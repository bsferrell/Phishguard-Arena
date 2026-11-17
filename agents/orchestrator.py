import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from core import db
from core.mastery import START
from core.models import WARNING_SIGNS
from core.picker import get_candidates, pick_next, want_legit, weakness

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
THINKING = "minimal"
TIMEOUT_MS = 15000
MAX_STEPS = 4           # most model turns allowed before falling back

INSTRUCTIONS = """You are the Orchestrator, the game master of a phishing
awareness training game. Your only job is to choose the next practice
message for the current learner.

Steps:
1. Call get_learner_state to see the learner's level and mastery.
2. Call get_candidates to get the shortlist of allowed scenarios.
3. Call select_scenario with one scenario_id from that shortlist and a
   one-sentence reason.

How to choose:
- Prefer scenarios that test the warning signs with the lowest mastery.
- Stay close to the learner's current difficulty level.
- If needs_legitimate is true, prefer a legitimate message, because
  learners must practice saying a real message is safe.
- You may only select an ID that appeared in get_candidates."""

DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_learner_state",
        description="Current difficulty level, mastery from 0 to 1 for "
                    "each warning sign, and whether a legitimate message "
                    "is due. Takes no arguments.",
    ),
    types.FunctionDeclaration(
        name="get_candidates",
        description="Up to 5 allowed next scenarios, ranked best first by "
                    "the game. Takes no arguments.",
    ),
    types.FunctionDeclaration(
        name="select_scenario",
        description="Choose the next scenario. The ID must come from "
                    "get_candidates.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "scenario_id": types.Schema(type="STRING"),
                "reason": types.Schema(
                    type="STRING",
                    description="One sentence explaining the choice"),
            },
            required=["scenario_id", "reason"],
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


class OrchestratorTools:
    """Tools bound to one learner. The model never sees the learner ID."""

    def __init__(self, conn, learner_id):
        self.conn = conn
        self.learner_id = learner_id
        self.shortlist = []        # IDs from the last get_candidates call
        self.chosen = None
        self.reason = None

    def get_learner_state(self):
        learner = db.get_learner(self.conn, self.learner_id)
        mastery = db.get_mastery(self.conn, self.learner_id)
        return {
            "level": learner["level"],
            "mastery": {s: round(mastery.get(s, START), 2)
                        for s in WARNING_SIGNS},
            "rounds_played": len(db.seen_scenario_ids(self.conn,
                                                      self.learner_id)),
            "needs_legitimate": want_legit(self.conn, self.learner_id),
        }

    def get_candidates(self):
        mastery = db.get_mastery(self.conn, self.learner_id)
        found = get_candidates(self.conn, self.learner_id)
        self.shortlist = [s.scenario_id for s in found]
        return {"candidates": [
            {
                "scenario_id": s.scenario_id,
                "difficulty": s.difficulty,
                "is_phishing": s.is_phishing,
                "tests_signs": s.warning_signs or s.decoy_signs,
                "weakness": round(weakness(s, mastery), 2),
            }
            for s in found
        ]}

    def select_scenario(self, scenario_id="", reason=""):
        if not self.shortlist:
            return {"accepted": False,
                    "error": "Call get_candidates first."}
        if scenario_id not in self.shortlist:
            return {"accepted": False,
                    "error": f"{scenario_id} is not on the shortlist. "
                             f"Choose one of {self.shortlist}."}
        self.chosen = scenario_id
        self.reason = reason
        return {"accepted": True}

    def dispatch(self, name, args):
        if name == "get_learner_state":
            return self.get_learner_state()
        if name == "get_candidates":
            return self.get_candidates()
        if name == "select_scenario":
            return self.select_scenario(args.get("scenario_id", ""),
                                        args.get("reason", ""))
        return {"error": f"Unknown function {name}"}


def choose_next(conn, learner_id) -> tuple[str, str, bool]:
    """Return (scenario_id, reason, True if the agent chose it)."""
    tools = OrchestratorTools(conn, learner_id)
    config = types.GenerateContentConfig(
        system_instruction=INSTRUCTIONS,
        tools=[types.Tool(function_declarations=DECLARATIONS)],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY")),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=THINKING),
        temperature=0.2,
    )
    contents = [types.Content(role="user", parts=[
        types.Part(text="Choose the next scenario for this learner.")])]

    start = time.perf_counter()
    try:
        for step in range(1, MAX_STEPS + 1):
            response = _get_client().models.generate_content(
                model=MODEL, contents=contents, config=config)
            content = response.candidates[0].content
            calls = [p.function_call for p in content.parts or []
                     if p.function_call]
            if not calls:
                break
            contents.append(content)          # keep the model's turn as is

            replies = []
            for call in calls:
                args = dict(call.args or {})
                result = tools.dispatch(call.name, args)
                db.log_agent(conn, learner_id, "orchestrator", call.name,
                             {"step": step, "args": args, "result": result})
                replies.append(types.Part.from_function_response(
                    name=call.name, response=result))

            if tools.chosen:
                print(f"Orchestrator: chose {tools.chosen} in {step} steps, "
                      f"{time.perf_counter() - start:.1f}s")
                db.log_agent(conn, learner_id, "orchestrator", "chosen",
                             {"scenario_id": tools.chosen,
                              "reason": tools.reason, "steps": step})
                return tools.chosen, tools.reason, True
            contents.append(types.Content(role="user", parts=replies))
        why = f"no valid choice after {MAX_STEPS} steps"
    except Exception as err:          # timeout, network, quota, bad key
        why = f"error: {str(err)[:120]}"

    fallback = pick_next(conn, learner_id).scenario_id
    print(f"Orchestrator: fallback to {fallback} ({why})")
    db.log_agent(conn, learner_id, "orchestrator", "fallback",
                 {"scenario_id": fallback, "why": why})
    return fallback, f"Fallback: {why}", False