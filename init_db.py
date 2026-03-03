import sqlite3

conn = sqlite3.connect("super_ai.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT UNIQUE,
    answer TEXT
)
""")

conn.commit()
conn.close()
print("✅ Database ready with Teach system")
