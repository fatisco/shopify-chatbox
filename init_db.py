import sqlite3
conn = sqlite3.connect('chat.db')
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, sender TEXT, text TEXT, ts TEXT)')
conn.commit()
conn.close()
print("Database ready.")
