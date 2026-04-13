import sqlite3
import random
from datetime import datetime

DB_NAME = "gemini_vault.db"

# Friendly word lists for random names
ADJECTIVES = ["sparkling", "brave", "swift", "quiet", "neon", "mighty", "clever"]
NOUNS = ["phoenix", "glitch", "nebula", "cipher", "wizard", "orbit", "atlas"]


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS sessions 
                          (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, created_at DATETIME)"""
        )
        cursor.execute("""CREATE TABLE IF NOT EXISTS messages 
                          (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, 
                           role TEXT, content TEXT, timestamp DATETIME,
                           FOREIGN KEY(session_id) REFERENCES sessions(id))""")


def generate_random_name():
    return (
        f"{random.choice(ADJECTIVES)}-{random.choice(NOUNS)}-{random.randint(100, 999)}"
    )


def get_or_create_session(name=None):
    if not name:
        name = generate_random_name()

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO sessions (name, created_at) VALUES (?, ?)",
            (name, datetime.now()),
        )
        cursor.execute("SELECT id, name FROM sessions WHERE name = ?", (name,))
        return cursor.fetchone()


def get_chat_history(session_id, window_size=12):
    """Token Reduction: Only fetch the last N messages (Sliding Window)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content FROM (
                SELECT role, content, timestamp FROM messages 
                WHERE session_id = ? 
                ORDER BY timestamp DESC LIMIT ?
            ) ORDER BY timestamp ASC
        """,
            (session_id, window_size),
        )
        rows = cursor.fetchall()
        return [{"role": r, "parts": [{"text": c}]} for r, c in rows]


def save_message(session_id, role, content):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now()),
        )


def list_all_sessions():
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            "SELECT name, created_at FROM sessions ORDER BY created_at DESC"
        ).fetchall()


# Add this to db_manager.py
def get_session_user_messages(session_id):
    """Fetches only user messages to populate terminal history."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM messages WHERE session_id = ? AND role = 'user' ORDER BY timestamp ASC",
            (session_id,),
        )
        return [row[0] for row in cursor.fetchall()]


# Add/Update these functions in db_manager.py


def get_last_n_messages(session_id):
    """Fetches the last N messages of a specific session for display."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT role, content FROM messages 
                WHERE session_id = ? 
                ORDER BY timestamp ASC
        """,
            (session_id,),
        )
        return cursor.fetchall()


def get_all_user_messages_global():
    """Fetches EVERY user prompt ever recorded for the global UP-arrow history."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM messages WHERE role = 'user' ORDER BY timestamp ASC"
        )
        return [row[0] for row in cursor.fetchall()]
