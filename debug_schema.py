import sqlite3
from pathlib import Path

schema_path = Path("pc-agent/src/database/schema.sql")
with open(schema_path, 'r', encoding='utf-8') as f:
    schema = f.read()

conn = sqlite3.connect(":memory:")
try:
    conn.executescript(schema)
    print("Schema executed successfully")
except sqlite3.Error as e:
    print(f"Schema execution failed: {e}")
    # Try executing statement by statement to find the error
    conn = sqlite3.connect(":memory:")
    statements = schema.split(';')
    for i, stmt in enumerate(statements):
        if not stmt.strip():
            continue
        try:
            conn.execute(stmt)
        except sqlite3.Error as e:
            print(f"Error in statement {i}: {e}")
            print(f"Statement: {stmt}")
            break
