from core import db
from core.content import load_passages, load_scenarios


def main():
    scenarios = load_scenarios()
    passages = load_passages()

    conn = db.connect()
    db.init_db(conn)

    for s in scenarios:
        conn.execute(
            "INSERT OR REPLACE INTO scenarios "
            "(scenario_id, difficulty, is_phishing, data) VALUES (?, ?, ?, ?)",
            (s.scenario_id, s.difficulty, int(s.is_phishing),
             s.model_dump_json()),
        )

    conn.execute("DELETE FROM knowledge_fts")
    for p in passages:
        conn.execute(
            "INSERT INTO knowledge_fts (policy_id, title, tags, body) "
            "VALUES (?, ?, ?, ?)",
            (p.policy_id, p.title, " ".join(p.tags), p.body),
        )
    conn.commit()

    n_s = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]
    n_k = conn.execute("SELECT COUNT(*) FROM knowledge_fts").fetchone()[0]
    print(f"Seeded {n_s} scenarios and {n_k} passages into {db.DB_PATH.name}")

    hits = conn.execute(
        "SELECT policy_id FROM knowledge_fts WHERE knowledge_fts MATCH ? "
        "ORDER BY bm25(knowledge_fts) LIMIT 3",
        ('"lookalike_domain"',),
    ).fetchall()
    print("Search test for lookalike_domain:", [h[0] for h in hits])


if __name__ == "__main__":
    main()