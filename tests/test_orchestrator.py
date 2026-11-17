from agents.orchestrator import OrchestratorTools
from core import db


def make_tools(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    db.init_db(conn)
    conn.executemany(
        "INSERT INTO scenarios VALUES (?, ?, ?, ?)",
        [(f"T-{i}", 1, 1,
          '{"scenario_id": "T-%d", "channel": "email", "is_phishing": true, '
          '"difficulty": 1, "subject": "s", "body": "b", '
          '"warning_signs": ["urgent_pressure"], '
          '"decoy_signs": ["odd_sender", "generic_greeting"], '
          '"policy_refs": []}' % i) for i in range(8)],
    )
    conn.commit()
    return OrchestratorTools(conn, db.create_learner(conn))


def test_select_before_candidates_is_rejected(tmp_path):
    tools = make_tools(tmp_path)
    assert tools.select_scenario("T-0", "x")["accepted"] is False


def test_off_list_id_is_rejected(tmp_path):
    tools = make_tools(tmp_path)
    shortlist = [c["scenario_id"]
                 for c in tools.get_candidates()["candidates"]]
    assert len(shortlist) == 5
    off_list = next(f"T-{i}" for i in range(8) if f"T-{i}" not in shortlist)
    assert tools.select_scenario(off_list, "x")["accepted"] is False
    assert tools.chosen is None


def test_shortlisted_id_is_accepted(tmp_path):
    tools = make_tools(tmp_path)
    first = tools.get_candidates()["candidates"][0]["scenario_id"]
    assert tools.select_scenario(first, "weakest sign")["accepted"] is True
    assert tools.chosen == first