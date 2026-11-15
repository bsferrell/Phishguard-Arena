from pydantic import BaseModel, Field

from core.models import Scenario


class Response(BaseModel):
    verdict_phishing: bool          # True means the learner said "phishing"
    selected: list[str] = []        # warning signs the learner ticked
    confidence: int = Field(ge=1, le=5)


class AttemptResult(BaseModel):
    correct: bool
    missed: list[str]
    false_hits: list[str]
    points: float

    @property
    def has_errors(self) -> bool:
        return not self.correct or bool(self.missed) or bool(self.false_hits)


def score(scenario: Scenario, response: Response) -> AttemptResult:
    real = set(scenario.warning_signs)
    picked = set(response.selected)

    missed = sorted(real - picked)
    false_hits = sorted(picked - real)
    correct = response.verdict_phishing == scenario.is_phishing

    weight = response.confidence / 5
    points = 10 if correct else -10 * weight
    points -= 2 * len(false_hits)

    return AttemptResult(
        correct=correct,
        missed=missed,
        false_hits=false_hits,
        points=round(points, 2),
    )