import sqlite3
sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE test USING fts5(body);")
print("FTS5 available.")