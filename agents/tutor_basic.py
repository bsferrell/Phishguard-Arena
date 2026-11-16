import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from core.content import load_passages
from core.models import Scenario
from core.scoring import AttemptResult

load_dotenv()

# Try the stronger model first, then the faster one, then the template.
MODELS = [
    ("gemini-3.5-flash-lite", "high"),
    ("gemini-3.5-flash-lite", "medium")
]
TIMEOUT_MS = 15000      # give up on a model after 15 seconds

INSTRUCTIONS = """You are the Tutor in a phishing awareness training game
for employees of a fictional company. The learner just answered a
practice message and made at least one mistake.

Write a short lesson of 80 to 120 words in plain text, no headings or
bullet points. Explain only the mistakes listed below. For each missed
warning sign, point to where it appears in the message. For each sign
the learner picked that was not there, explain briefly why it does not
apply. Base your advice only on the company policy passages provided,
and mention the policy ID you are drawing on. Be encouraging and
direct. Do not invent new policies."""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
    return _client


def _policy_text(scenario: Scenario) -> str:
    wanted = set(scenario.policy_refs) | {"POLICY-REP01"}
    passages = [p for p in load_passages() if p.policy_id in wanted]
    return "\n\n".join(f"{p.policy_id}: {p.title}\n{p.body}" for p in passages)


def _fallback(scenario: Scenario, result: AttemptResult) -> str:
    parts = []
    if not result.correct:
        kind = "a phishing attempt" if scenario.is_phishing else "legitimate"
        parts.append(f"This message was {kind}.")
    if result.missed:
        parts.append("Signs you missed: "
                     + ", ".join(s.replace("_", " ") for s in result.missed)
                     + ".")
    if result.false_hits:
        parts.append("Signs you picked that were not present: "
                     + ", ".join(s.replace("_", " ")
                                 for s in result.false_hits) + ".")
    if scenario.policy_refs:
        parts.append("Review " + ", ".join(scenario.policy_refs) + ".")
    return " ".join(parts)


def write_lesson(scenario: Scenario, result: AttemptResult) -> tuple[str, bool]:
    """Return (lesson text, True if it came from the model)."""
    answer = "phishing" if scenario.is_phishing else "legitimate"
    prompt = f"""Message the learner saw:
Subject: {scenario.subject}
{scenario.body}

Correct answer: {answer}
Learner's verdict was {"correct" if result.correct else "wrong"}.
Warning signs the learner missed: {result.missed or "none"}
Signs the learner picked that were not present: {result.false_hits or "none"}

Company policy passages:
{_policy_text(scenario)}"""

    for model, thinking in MODELS:
        start = time.perf_counter()
        try:
            response = _get_client().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=INSTRUCTIONS,
                    temperature=0.4,
                    max_output_tokens=4096,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=thinking),
                ),
            )
            text = (response.text or "").strip()
            print(f"Tutor: {model} took {time.perf_counter() - start:.1f}s")
            if text:
                return text, True
        except Exception as err:      # timeout, network, quota, bad key
            print(f"Tutor: {model} failed after "
                  f"{time.perf_counter() - start:.1f}s: {err}")
    return _fallback(scenario, result), False