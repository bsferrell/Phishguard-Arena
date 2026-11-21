from types import SimpleNamespace

import agents.orchestrator as orchestrator
import agents.tutor as tutor
from core import db
from core.game import play_round
from core.scoring import Response
from tests.test_scoring import PHISH


class BrokenModels:
    """Stands in for the Gemini client and fails every call."""

    def generate_content(self, **kwargs):
        raise TimeoutError("simulated API outage")


def setup(tmp_path, monkeypatch):
    broken = SimpleNamespace(models=BrokenModels())
    monkeypatch.setattr(orchestrator, "_get_client", lambda: broken)
    monkeypatch.setattr(tutor, "_get_client", lambda: broken)

    conn = db.connect(tmp_path / "test.db")
    db.init_db(conn)
    conn.execute("INSERT INTO scenarios VALUES (?, ?, ?, ?)",
                 (PHISH.scenario_id, PHISH.difficulty, 1,
                  PHISH.model_dump_json()))
    conn.commit()
    return conn, db.create_learner(conn)


def test_orchestrator_falls_back_when_api_fails(tmp_path, monkeypatch):
    conn, learner_id = setup(tmp_path, monkeypatch)
    scenario_id, reason, from_agent = orchestrator.choose_next(conn, learner_id)
    assert scenario_id == PHISH.scenario_id
    assert from_agent is False
    assert "simulated API outage" in reason


def test_tutor_falls_back_when_api_fails(tmp_path, monkeypatch):
    conn, learner_id = setup(tmp_path, monkeypatch)
    attempt_id, result = play_round(
        conn, learner_id, PHISH.scenario_id,
        Response(verdict_phishing=False, confidence=5))
    text, from_model = tutor.write_lesson(conn, learner_id, attempt_id,
                                          PHISH, result)
    assert from_model is False
    assert "phishing attempt" in text
    assert "Lookalike domain" in text