import sqlite3
from datetime import datetime, timezone

DB_PATH = "events.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS webhook_events (
            delivery_id TEXT PRIMARY KEY,
            event TEXT NOT NULL,
            action TEXT,
            issue_number INTEGER,
            timestamp TEXT NOT NULL
        )
        """)
        conn.commit()

def save_event(delivery_id, event, action, issue_number):
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute(
                "INSERT INTO webhook_events VALUES (?, ?, ?, ?, ?)",
                (delivery_id, event, action, issue_number,
                 datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def list_events(limit=50):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """SELECT delivery_id,event,action,issue_number,timestamp
               FROM webhook_events ORDER BY timestamp DESC LIMIT ?""",
            (min(limit, 100),)
        ).fetchall()
    return [
        {"id": r[0], "event": r[1], "action": r[2],
         "issue_number": r[3], "timestamp": r[4]}
        for r in rows
    ]
