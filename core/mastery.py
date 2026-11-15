from core.models import Scenario
from core.scoring import AttemptResult

ALPHA = 0.3        # each round moves the score 30 percent toward the result
START = 0.5        # starting mastery for a sign the learner has not seen
WINDOW = 5         # how many recent rounds the level rule looks at
MIN_LEVEL = 1
MAX_LEVEL = 5


def update_score(old: float, result: float) -> float:
    return round(old + ALPHA * (result - old), 4)


def update_mastery(current: dict, scenario: Scenario,
                   result: AttemptResult) -> dict:
    """Return a new mastery dict after one round."""
    outcomes = {}
    for sign in scenario.warning_signs:
        outcomes[sign] = 0.0 if sign in result.missed else 1.0
    for sign in result.false_hits:
        outcomes[sign] = 0.0       # ticking a sign that is not there

    new = dict(current)
    for sign, outcome in outcomes.items():
        new[sign] = update_score(current.get(sign, START), outcome)
    return new


def next_level(level: int, recent: list[bool]) -> int:
    """recent holds results since the last level change, newest first."""
    if len(recent) < WINDOW:
        return level
    wins = sum(recent[:WINDOW])
    if wins >= 4:
        return min(level + 1, MAX_LEVEL)
    if wins <= 2:
        return max(level - 1, MIN_LEVEL)
    return level