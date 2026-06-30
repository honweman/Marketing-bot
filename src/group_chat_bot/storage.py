from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class ConversationStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                user_name TEXT,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_created
            ON messages(chat_id, created_at)
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER,
                user_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_activity_chat_created
            ON user_activity(chat_id, created_at)
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (chat_id, key)
            )
            """
        )
        self.conn.commit()

    def add_message(self, chat_id: int, role: str, content: str, user_name: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO messages(chat_id, role, user_name, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (chat_id, role, user_name, content, time.time()),
        )
        self.conn.commit()

    def recent_messages(self, chat_id: int, limit: int) -> list[dict[str, str]]:
        rows = self.conn.execute(
            """
            SELECT role, user_name, content
            FROM messages
            WHERE chat_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()
        rows = list(reversed(rows))

        messages: list[dict[str, str]] = []
        for row in rows:
            content = row["content"]
            if row["role"] == "user" and row["user_name"]:
                content = f"{row['user_name']}: {content}"
            messages.append({"role": row["role"], "content": content})
        return messages

    def clear_chat(self, chat_id: int) -> None:
        self.conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        self.conn.commit()

    def record_activity(self, chat_id: int, user_id: int | None, user_name: str, event_type: str = "message") -> None:
        self.conn.execute(
            "INSERT INTO user_activity(chat_id, user_id, user_name, event_type, created_at) VALUES (?, ?, ?, ?, ?)",
            (chat_id, user_id, user_name, event_type, time.time()),
        )
        self.conn.commit()

    def leaderboard(self, chat_id: int, days: int, limit: int = 10) -> list[dict[str, int | str]]:
        since = time.time() - max(1, days) * 86400
        rows = self.conn.execute(
            """
            SELECT COALESCE(user_id, 0) AS user_id,
                   user_name,
                   COUNT(*) AS score
            FROM user_activity
            WHERE chat_id = ? AND created_at >= ?
            GROUP BY COALESCE(user_id, 0), user_name
            ORDER BY score DESC, user_name ASC
            LIMIT ?
            """,
            (chat_id, since, limit),
        ).fetchall()
        return [
            {"user_id": int(row["user_id"]), "user_name": row["user_name"], "score": int(row["score"])}
            for row in rows
        ]

    def get_chat_setting(self, chat_id: int, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM chat_settings WHERE chat_id = ? AND key = ?",
            (chat_id, key),
        ).fetchone()
        return str(row["value"]) if row is not None else None

    def set_chat_setting(self, chat_id: int, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO chat_settings(chat_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id, key)
            DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (chat_id, key, value, time.time()),
        )
        self.conn.commit()

    def delete_chat_setting(self, chat_id: int, key: str) -> None:
        self.conn.execute("DELETE FROM chat_settings WHERE chat_id = ? AND key = ?", (chat_id, key))
        self.conn.commit()
