import sqlite3
import random
from datetime import datetime
from pure_chat.fs import database_path

# Friendly word lists for random names
ADJECTIVES = ["sparkling", "brave", "swift", "quiet", "neon", "mighty", "clever"]
NOUNS = ["phoenix", "glitch", "nebula", "cipher", "wizard", "orbit", "atlas"]

DB_NAME = database_path()


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

        # Create FTS5 virtual table for full-text search
        cursor.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content, role, session_id, content_rowid=rowid
            )""")

        # Create triggers to keep FTS in sync
        cursor.execute(
            """CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content, role, session_id)
                VALUES (new.id, new.content, new.role, new.session_id);
            END"""
        )
        cursor.execute(
            """CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                DELETE FROM messages_fts WHERE rowid = old.id;
            END"""
        )
        cursor.execute(
            """CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                UPDATE messages_fts SET content = new.content, role = new.role, session_id = new.session_id
                WHERE rowid = new.id;
            END"""
        )

        # Backfill: Index existing messages that aren't in FTS yet
        cursor.execute("""INSERT INTO messages_fts(rowid, content, role, session_id)
               SELECT m.id, m.content, m.role, m.session_id
               FROM messages m
               LEFT JOIN messages_fts fts ON m.id = fts.rowid
               WHERE fts.rowid IS NULL""")


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


def rename_session(session_id, new_name):
    """Rename a session. Returns the new name, or None if the name is already taken."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE sessions SET name = ? WHERE id = ?", (new_name, session_id))
            if cursor.rowcount == 0:
                return None
            return new_name
        except sqlite3.IntegrityError:
            return None


def delete_session(session_id):
    """Delete a session and all its messages."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def _escape_fts_token(token: str) -> str:
    """Escape FTS5 special characters in a single token."""
    # Remove characters that have special meaning in FTS5 MATCH expressions
    special = '" * ( ) : ^'
    for ch in special:
        token = token.replace(ch, "")
    return token


def parse_search_query(query: str) -> str:
    """
    Parse search query for FTS5 syntax.
    - Quoted phrases: "exact match" → use phrase search
    - Unquoted: use prefix search per word for fuzzy matching
    """
    if not query or not query.strip():
        return ""

    query = query.strip()

    # Check if query is wrapped in quotes (exact phrase)
    if query.startswith('"') and query.endswith('"') and len(query) > 2:
        # Remove quotes for phrase search (FTS5 handles phrases natively)
        inner = query[1:-1]
        return f'"{inner}"'

    # Fuzzy search: add * at end of each word for prefix matching
    tokens = query.split()
    escaped = [_escape_fts_token(t) for t in tokens]
    # Filter out empty tokens after escaping
    escaped = [t for t in escaped if t]
    if not escaped:
        return ""
    return " ".join(f"{t}*" for t in escaped)


# Invisible sentinel markers for FTS5 snippets (won't conflict with Rich markup)
_MARK_START = "\x01"
_MARK_END = "\x02"


def search_messages(query: str, limit: int = 10):
    """
    Search messages using FTS5 with snippet extraction.
    Deduplicates by session (best match per session).
    Returns list of dicts: [{session_id, session_name, content_snippet, timestamp, role}]
    """
    if not query or not query.strip():
        return []

    fts_query = parse_search_query(query)

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # Search FTS table and join with messages for metadata
        # Use invisible sentinel markers to avoid Rich markup conflicts
        cursor.execute(
            """
            SELECT 
                m.session_id,
                s.name as session_name,
                snippet(messages_fts, -1, ?, ?, '...', 64) as snippet,
                m.timestamp,
                m.role
            FROM messages_fts
            JOIN messages m ON messages_fts.rowid = m.id
            JOIN sessions s ON m.session_id = s.id
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (_MARK_START, _MARK_END, fts_query, limit),
        )

        # Deduplicate by session_id: keep the best (first) match per session
        seen_sessions = set()
        results = []
        for row in cursor.fetchall():
            sid = row[0]
            if sid in seen_sessions:
                continue
            seen_sessions.add(sid)

            # Replace sentinel markers with Rich markup tags
            snippet = (
                row[2]
                .replace(_MARK_START, "[bold green]")
                .replace(_MARK_END, "[/bold green]")
            )

            results.append(
                {
                    "session_id": sid,
                    "session_name": row[1],
                    "snippet": snippet,
                    "timestamp": row[3],
                    "role": row[4],
                }
            )

        return results
