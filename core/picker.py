from core import db
from core.mastery import START
from core.models import Scenario

LEGIT_SHARE = 1 / 3     # roughly one in three messages should be legitimate


def weakness(scenario: Scenario, mastery: dict) -> float:
    """Higher means the learner is weaker on what this scenario tests."""
    signs = scenario.warning_signs or scenario.decoy_signs
    return sum(1 - mastery.get(s, START) for s in signs) / len(signs)


def want_legit(conn, learner_id: str) -> bool:
    rows = conn.execute(
        "SELECT s.is_phishing FROM attempts a "
        "JOIN scenarios s ON s.scenario_id = a.scenario_id "
        "WHERE a.learner_id = ?",
        (learner_id,),
    ).fetchall()
    if not rows:
        return False                # open with a phishing message
    legit = sum(1 for r in rows if not r["is_phishing"])
    return legit / len(rows) < LEGIT_SHARE


def get_candidates(conn, learner_id: str, limit: int = 5) -> list[Scenario]:
    """Ranked shortlist of good next scenarios. Best first."""
    learner = db.get_learner(conn, learner_id)
    level = learner["level"]
    mastery = db.get_mastery(conn, learner_id)
    seen = db.seen_scenario_ids(conn, learner_id)

    pool = [s for s in db.all_scenarios(conn) if s.scenario_id not in seen]
    if not pool:                    # everything seen, start reusing
        pool = db.all_scenarios(conn)

    legit_first = want_legit(conn, learner_id)

    def rank(s: Scenario):
        type_match = (not s.is_phishing) == legit_first
        return (
            not type_match,                 # preferred type first
            abs(s.difficulty - level),      # closest to current level
            -weakness(s, mastery),          # weakest signs first
            s.scenario_id,                  # stable tie breaker
        )

    return sorted(pool, key=rank)[:limit]


def pick_next(conn, learner_id: str) -> Scenario:
    return get_candidates(conn, learner_id)[0]