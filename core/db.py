import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.models import Scenario

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "phishguard.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id  TEXT PRIMARY KEY,
    difficulty   INTEGER NOT NULL,
    is_phishing  INTEGER NOT NULL,
    data         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learners (
    learner_id           TEXT PRIMARY KEY,
    created_at           TEXT NOT NULL,
    level                INTEGER NOT NULL DEFAULT 1,
    level_start_attempt  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id        TEXT NOT NULL REFERENCES learners(learner_id),
    scenario_id       TEXT NOT NULL REFERENCES scenarios(scenario_id),
    created_at        TEXT NOT NULL,
    verdict_phishing  INTEGER NOT NULL,
    selected          TEXT NOT NULL,
    confidence        INTEGER NOT NULL,
    correct           INTEGER NOT NULL,
    missed            TEXT NOT NULL,
    false_hits        TEXT NOT NULL,
    points            REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS mastery (
    learner_id  TEXT NOT NULL REFERENCES learners(learner_id),
    sign        TEXT NOT NULL,
    score       REAL NOT NULL,
    PRIMARY KEY (learner_id, sign)
);

CREATE TABLE IF NOT EXISTS agent_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  TEXT,
    created_at  TEXT NOT NULL,
    agent       TEXT NOT NULL,
    action      TEXT NOT NULL,
    detail      TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    policy_id UNINDEXED, title, tags, body
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


# Learners

def create_learner(conn) -> str:
    learner_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO learners (learner_id, created_at) VALUES (?, ?)",
        (learner_id, _now()),
    )
    conn.commit()
    return learner_id


def get_learner(conn, learner_id: str):
    return conn.execute(
        "SELECT * FROM learners WHERE learner_id = ?", (learner_id,)
    ).fetchone()


def set_level(conn, learner_id: str, level: int, attempt_id: int) -> None:
    conn.execute(
        "UPDATE learners SET level = ?, level_start_attempt = ? "
        "WHERE learner_id = ?",
        (level, attempt_id, learner_id),
    )
    conn.commit()


# Scenarios

def all_scenarios(conn) -> list[Scenario]:
    rows = conn.execute("SELECT data FROM scenarios").fetchall()
    return [Scenario(**json.loads(r["data"])) for r in rows]


def get_scenario(conn, scenario_id: str) -> Scenario | None:
    row = conn.execute(
        "SELECT data FROM scenarios WHERE scenario_id = ?", (scenario_id,)
    ).fetchone()
    return Scenario(**json.loads(row["data"])) if row else None


def seen_scenario_ids(conn, learner_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT scenario_id FROM attempts WHERE learner_id = ?",
        (learner_id,),
    ).fetchall()
    return {r["scenario_id"] for r in rows}


# Attempts

def save_attempt(conn, learner_id, scenario_id, response, result) -> int:
    cur = conn.execute(
        "INSERT INTO attempts (learner_id, scenario_id, created_at, "
        "verdict_phishing, selected, confidence, correct, missed, "
        "false_hits, points) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            learner_id, scenario_id, _now(),
            int(response.verdict_phishing), json.dumps(response.selected),
            response.confidence, int(result.correct),
            json.dumps(result.missed), json.dumps(result.false_hits),
            result.points,
        ),
    )
    conn.commit()
    return cur.lastrowid


def recent_results(conn, learner_id: str) -> list[bool]:
    """Results since the learner's last level change, newest first."""
    learner = get_learner(conn, learner_id)
    rows = conn.execute(
        "SELECT correct FROM attempts WHERE learner_id = ? "
        "AND attempt_id > ? ORDER BY attempt_id DESC LIMIT 5",
        (learner_id, learner["level_start_attempt"]),
    ).fetchall()
    return [bool(r["correct"]) for r in rows]


# Mastery

def get_mastery(conn, learner_id: str) -> dict:
    rows = conn.execute(
        "SELECT sign, score FROM mastery WHERE learner_id = ?", (learner_id,)
    ).fetchall()
    return {r["sign"]: r["score"] for r in rows}


def save_mastery(conn, learner_id: str, scores: dict) -> None:
    conn.executemany(
        "INSERT INTO mastery (learner_id, sign, score) VALUES (?, ?, ?) "
        "ON CONFLICT (learner_id, sign) DO UPDATE SET score = excluded.score",
        [(learner_id, sign, s) for sign, s in scores.items()],
    )
    conn.commit()


# Agent log

def log_agent(conn, learner_id, agent: str, action: str, detail=None) -> None:
    conn.execute(
        "INSERT INTO agent_log (learner_id, created_at, agent, action, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (learner_id, _now(), agent, action, json.dumps(detail)),
    )
    conn.commit()