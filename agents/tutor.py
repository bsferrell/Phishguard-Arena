import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from core import db
from core.models import Scenario
from core.retrieval import search_knowledge
from core.scoring import AttemptResult

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
THINKING = "minimal"
TIMEOUT_MS = 15000
MAX_STEPS = 5           # model turns allowed before falling back
MAX_SUBMITS = 2         # first try plus one retry
MAX_WORDS = 160
QUOTE_AFTER = 2         # switch to quoted style once a sign is missed twice


class SignNote(BaseModel):
    sign: str
    note: str
    quote: str = ""     # exact words from the message, quoted style only


class MicroLesson(BaseModel):
    headline: str
    notes: list[SignNote]
    next_time: str
    policy_ids: list[str]


INSTRUCTIONS = """You are the Tutor in a phishing awareness training game
for employees of a fictional company. The learner just made a mistake on
a practice message. Write a short lesson about that mistake.

Steps:
1. Call get_attempt_result to see the message, the correct answer, the
   learner's mistakes, and the required style.
2. Call search_knowledge to find company policy for the mistakes. Search
   using the warning sign names, for example "lookalike_domain".
3. Call submit_lesson.

Lesson rules:
- headline: one sentence saying whether the message was phishing or
  legitimate and what the main mistake was.
- notes: one note for each sign in missed and each sign in false_hits,
  and no others. Each note is one or two plain sentences.
- If style is "quoted", every note for a missed sign must include a
  quote copied exactly from the message showing where the sign appears.
- next_time: one practical habit for next time.
- policy_ids: only IDs returned by search_knowledge.
- Base advice only on the policy text you retrieved. Keep the whole
  lesson under 160 words. If submit_lesson returns problems, fix them
  and submit again."""

SIGN_NOTE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "sign": types.Schema(type="STRING"),
        "note": types.Schema(type="STRING"),
        "quote": types.Schema(type="STRING"),
    },
    required=["sign", "note"],
)

DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_attempt_result",
        description="The message the learner saw, the correct answer, and "
                    "the mistakes the game already scored. Takes no "
                    "arguments.",
    ),
    types.FunctionDeclaration(
        name="search_knowledge",
        description="Search company security policy. Returns the 3 best "
                    "matching passages with their policy IDs.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"query": types.Schema(
                type="STRING",
                description="Keywords, such as a warning sign name")},
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="submit_lesson",
        description="Submit the finished lesson for checking.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "headline": types.Schema(type="STRING"),
                "notes": types.Schema(type="ARRAY", items=SIGN_NOTE_SCHEMA),
                "next_time": types.Schema(type="STRING"),
                "policy_ids": types.Schema(
                    type="ARRAY", items=types.Schema(type="STRING")),
            },
            required=["headline", "notes", "next_time", "policy_ids"],
        ),
    ),
]

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
    return _client


def choose_style(conn, learner_id: str, result: AttemptResult) -> str:
    if any(db.times_missed(conn, learner_id, s) >= QUOTE_AFTER
           for s in result.missed):
        return "quoted"
    return "general"


def validate_lesson(lesson: MicroLesson, scenario: Scenario,
                    result: AttemptResult, retrieved: set[str],
                    style: str) -> list[str]:
    """Return a list of problems. An empty list means the lesson passes."""
    problems = []
    wrong = set(result.missed) | set(result.false_hits)
    noted = {n.sign for n in lesson.notes}

    if not lesson.policy_ids:
        problems.append("policy_ids is empty.")
    for pid in lesson.policy_ids:
        if pid not in retrieved:
            problems.append(f"{pid} was not returned by search_knowledge.")
    for sign in noted - wrong:
        problems.append(f"{sign} is not one of the learner's mistakes.")
    for sign in wrong - noted:
        problems.append(f"Add a note for {sign}.")
    if style == "quoted":
        body = scenario.body.lower()
        for n in lesson.notes:
            if n.sign in result.missed:
                if not n.quote.strip():
                    problems.append(f"The note for {n.sign} needs a quote.")
                elif n.quote.strip().lower() not in body:
                    problems.append(f"The quote for {n.sign} is not in "
                                    "the message word for word.")
    words = len(format_lesson(lesson).split())
    if words > MAX_WORDS:
        problems.append(f"Lesson is {words} words. Keep it under {MAX_WORDS}.")
    return problems


def label(sign: str) -> str:
    return sign.replace("_", " ").capitalize()


def format_lesson(lesson: MicroLesson) -> str:
    lines = [lesson.headline, ""]
    for n in lesson.notes:
        lines.append(f"{label(n.sign)}: {n.note}")
        if n.quote:
            lines.append(f'    In the message: "{n.quote}"')
    lines += ["", f"Next time: {lesson.next_time}",
              f"Policy: {', '.join(lesson.policy_ids)}"]
    return "\n".join(lines)


def template_lesson(scenario: Scenario, result: AttemptResult) -> str:
    parts = []
    if not result.correct:
        kind = "a phishing attempt" if scenario.is_phishing else "legitimate"
        parts.append(f"This message was {kind}.")
    if result.missed:
        parts.append("Signs you missed: "
                     + ", ".join(label(s) for s in result.missed) + ".")
    if result.false_hits:
        parts.append("Signs you picked that were not present: "
                     + ", ".join(label(s) for s in result.false_hits) + ".")
    if scenario.policy_refs:
        parts.append("Review " + ", ".join(scenario.policy_refs) + ".")
    return " ".join(parts)


class TutorTools:
    """Tools bound to one attempt. The model never sees the learner ID."""

    def __init__(self, conn, scenario, result, style):
        self.conn = conn
        self.scenario = scenario
        self.result = result
        self.style = style
        self.retrieved = set()     # policy IDs search has returned
        self.submits = 0
        self.lesson = None

    def get_attempt_result(self):
        s, r = self.scenario, self.result
        return {
            "message": f"Subject: {s.subject}\n{s.body}",
            "correct_answer": "phishing" if s.is_phishing else "legitimate",
            "verdict_correct": r.correct,
            "missed": r.missed,
            "false_hits": r.false_hits,
            "style": self.style,
        }

    def search_knowledge(self, query=""):
        hits = search_knowledge(self.conn, query)
        self.retrieved |= {h["policy_id"] for h in hits}
        return {"results": hits}

    def submit_lesson(self, args):
        self.submits += 1
        try:
            lesson = MicroLesson(**args)
        except ValidationError as err:
            return {"accepted": False, "problems": [str(err)[:300]]}
        problems = validate_lesson(lesson, self.scenario, self.result,
                                   self.retrieved, self.style)
        if problems:
            return {"accepted": False, "problems": problems}
        self.lesson = lesson
        return {"accepted": True}

    def dispatch(self, name, args):
        if name == "get_attempt_result":
            return self.get_attempt_result()
        if name == "search_knowledge":
            return self.search_knowledge(args.get("query", ""))
        if name == "submit_lesson":
            return self.submit_lesson(args)
        return {"error": f"Unknown function {name}"}


def write_lesson(conn, learner_id: str, attempt_id: int,
                 scenario: Scenario, result: AttemptResult) -> tuple[str, bool]:
    """Return (lesson text, True if it came from the model)."""
    style = choose_style(conn, learner_id, result)
    tools = TutorTools(conn, scenario, result, style)
    config = types.GenerateContentConfig(
        system_instruction=INSTRUCTIONS,
        tools=[types.Tool(function_declarations=DECLARATIONS)],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY")),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=THINKING),
        temperature=0.4,
        max_output_tokens=2048,
    )
    contents = [types.Content(role="user", parts=[
        types.Part(text="Write a lesson for the learner's latest attempt.")])]

    def log(action, detail):
        db.log_agent(conn, learner_id, "tutor", action,
                     {"attempt_id": attempt_id, **detail})

    start = time.perf_counter()
    try:
        for step in range(1, MAX_STEPS + 1):
            response = _get_client().models.generate_content(
                model=MODEL, contents=contents, config=config)
            cand = response.candidates[0] if response.candidates else None
            content = cand.content if cand else None
            calls = [p.function_call for p in (content.parts or [])
                     if p.function_call] if content else []
            if not calls:
                reason = cand.finish_reason.name if cand and cand.finish_reason else "NONE"
                why = f"no function call (finish={reason})"
                break
            contents.append(content)

            replies = []
            for call in calls:
                args = dict(call.args or {})
                reply = tools.dispatch(call.name, args)
                log(call.name, {"step": step, "args": args, "result": reply})
                replies.append(types.Part.from_function_response(
                    name=call.name, response=reply))

            if tools.lesson:
                print(f"Tutor: {style} lesson accepted in {step} steps, "
                      f"{time.perf_counter() - start:.1f}s")
                log("accepted", {"style": style, "steps": step,
                                 "lesson": tools.lesson.model_dump()})
                return format_lesson(tools.lesson), True
            if tools.submits >= MAX_SUBMITS:
                why = "lesson failed validation twice"
                break
            contents.append(types.Content(role="user", parts=replies))
        else:
            why = f"no accepted lesson after {MAX_STEPS} steps"
    except Exception as err:          # timeout, network, quota, bad key
        why = f"error: {str(err)[:120]}"

    print(f"Tutor: template fallback ({why})")
    log("fallback", {"why": why})
    return template_lesson(scenario, result), False