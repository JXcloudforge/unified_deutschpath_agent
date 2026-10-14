from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4


class ChatRepository:
    """Adapted from 03_deutsch_chat: separate sessions/messages/attachments tables."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS chat_sessions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,title TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS chat_messages(id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,role TEXT NOT NULL CHECK(role IN ('user','assistant')),content TEXT NOT NULL,seq INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(session_id,seq));
            CREATE TABLE IF NOT EXISTS attachments(id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,filename TEXT NOT NULL,file_type TEXT NOT NULL,stored_path TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """)

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def create_session(self, user_id: str) -> dict:
        session_id = str(uuid4())
        with self._connection() as conn:
            conn.execute("INSERT INTO chat_sessions(id,user_id,title) VALUES(?,?,?)", (session_id, user_id, "New Chat"))
        return self.get_session(user_id, session_id)

    def get_session(self, user_id: str, session_id: str) -> dict:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM chat_sessions WHERE id=? AND user_id=?", (session_id, user_id)).fetchone()
        if row is None:
            raise KeyError("Session not found")
        return dict(row)

    def list_sessions(self, user_id: str) -> list[dict]:
        """Adapt 03 SessionRepository.list_sessions to 04's dict contract."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id,user_id,title,created_at,updated_at FROM chat_sessions WHERE user_id=? ORDER BY updated_at DESC,id DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def rename_session(self, user_id: str, session_id: str, title: str) -> dict:
        """Update a persistent title only when the session belongs to this user."""
        title = title.strip() if isinstance(title, str) else ""
        if not title or len(title) > 100:
            raise ValueError("title must contain between 1 and 100 characters")
        with self._connection() as conn:
            cursor = conn.execute(
                "UPDATE chat_sessions SET title=?,updated_at=STRFTIME('%Y-%m-%d %H:%M:%f','now') WHERE id=? AND user_id=?",
                (title, session_id, user_id),
            )
        if cursor.rowcount != 1:
            raise KeyError("Session not found")
        return self.get_session(user_id, session_id)

    def add_message(self, user_id: str, session_id: str, role: str, content: str,
                    *, preserve_session_title: bool = False) -> dict:
        self.get_session(user_id, session_id)
        with self._connection() as conn:
            sequence = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM chat_messages WHERE session_id=?", (session_id,)).fetchone()[0]
            message_id = str(uuid4())
            conn.execute("INSERT INTO chat_messages(id,session_id,role,content,seq) VALUES(?,?,?,?,?)", (message_id, session_id, role, content, sequence))
            auto_title = int(not preserve_session_title)
            conn.execute("UPDATE chat_sessions SET updated_at=STRFTIME('%Y-%m-%d %H:%M:%f','now'),title=CASE WHEN title='New Chat' AND ?=1 AND ?=1 THEN ? ELSE title END WHERE id=?", (sequence, auto_title, content[:40], session_id))
            row = conn.execute("SELECT * FROM chat_messages WHERE id=?", (message_id,)).fetchone()
        return dict(row)

    def messages(self, user_id: str, session_id: str) -> list[dict]:
        self.get_session(user_id, session_id)
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM chat_messages WHERE session_id=? ORDER BY seq", (session_id,)).fetchall()
        return [dict(row) for row in rows]

    def add_attachment(self, user_id: str, session_id: str, filename: str, file_type: str, stored_path: str) -> None:
        self.get_session(user_id, session_id)
        with self._connection() as conn:
            conn.execute("INSERT INTO attachments(id,session_id,filename,file_type,stored_path) VALUES(?,?,?,?,?)", (str(uuid4()), session_id, filename, file_type, stored_path))

    def attachments(self, user_id: str, session_id: str) -> list[dict]:
        self.get_session(user_id, session_id)
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM attachments WHERE session_id=? ORDER BY created_at", (session_id,)).fetchall()
        return [dict(row) for row in rows]
