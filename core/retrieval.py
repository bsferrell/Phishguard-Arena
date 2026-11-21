import re

TOP_K = 3


def search_knowledge(conn, query: str, k: int = TOP_K) -> list[dict]:
    """Full-text search over the policy passages, best match first."""
    words = re.findall(r"[A-Za-z0-9_]+", query)
    if not words:
        return []
    # Quote every word so symbols and FTS5 keywords cannot break the query,
    # and join with OR so any matching word counts. bm25 does the ranking.
    match = " OR ".join(f'"{w}"' for w in words)
    rows = conn.execute(
        "SELECT policy_id, title, body FROM knowledge_fts "
        "WHERE knowledge_fts MATCH ? ORDER BY bm25(knowledge_fts) LIMIT ?",
        (match, k),
    ).fetchall()
    return [dict(r) for r in rows]