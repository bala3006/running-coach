import os
import sqlite3
from contextlib import closing
from pathlib import Path


def _database_path() -> Path:
    configured = os.getenv("RUNNING_COACH_DB")
    return Path(configured).expanduser() if configured else Path.home() / ".running-coach" / "coach.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS messages_session_id ON messages(session_id, id)")
    return connection


def get_history(session_id: str, limit: int = 30) -> list[dict[str, str]]:
    with closing(_connect()) as connection:
        with connection:
            rows = connection.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]


def save_exchange(session_id: str, user_message: str, assistant_message: str) -> None:
    with closing(_connect()) as connection:
        with connection:
            connection.executemany(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                [
                    (session_id, "user", user_message),
                    (session_id, "assistant", assistant_message),
                ],
            )
