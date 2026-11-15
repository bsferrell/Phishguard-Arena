from core import db
from core.mastery import next_level, update_mastery
from core.scoring import Response, score


def play_round(conn, learner_id: str, scenario_id: str, response: Response):
    """Score one answer and save everything it changes."""
    scenario = db.get_scenario(conn, scenario_id)
    result = score(scenario, response)

    attempt_id = db.save_attempt(conn, learner_id, scenario_id,
                                 response, result)

    mastery = db.get_mastery(conn, learner_id)
    db.save_mastery(conn, learner_id,
                    update_mastery(mastery, scenario, result))

    learner = db.get_learner(conn, learner_id)
    new_level = next_level(learner["level"],
                           db.recent_results(conn, learner_id))
    if new_level != learner["level"]:
        db.set_level(conn, learner_id, new_level, attempt_id)

    return attempt_id, result