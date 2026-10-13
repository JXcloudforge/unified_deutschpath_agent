from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import LearningEvent, UserState


class UserStateRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_states (user_id TEXT PRIMARY KEY, current_level TEXT, target_level TEXT, learning_goal TEXT, learning_preferences TEXT);
            CREATE TABLE IF NOT EXISTS learning_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, event_type TEXT NOT NULL, item TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """)

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def get(self, user_id: str) -> UserState:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM user_states WHERE user_id=?", (user_id,)).fetchone()
        return UserState(user_id, None, None, None, None) if row is None else UserState(**dict(row))

    def update(self, user_id: str, **values: str | None) -> UserState:
        current = self.get(user_id)
        payload = {key: values.get(key, getattr(current, key)) for key in ("current_level", "target_level", "learning_goal", "learning_preferences")}
        with self._connection() as conn:
            conn.execute("INSERT INTO user_states(user_id,current_level,target_level,learning_goal,learning_preferences) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET current_level=excluded.current_level,target_level=excluded.target_level,learning_goal=excluded.learning_goal,learning_preferences=excluded.learning_preferences", (user_id, *payload.values()))
        return self.get(user_id)

    def add_event(self, user_id: str, event_type: str, item: str, result: str | None = None) -> LearningEvent:
        # Adapted from 02 CustomerRepository.add_learning_event; 04 owns the schema.
        with self._connection() as conn:
            cursor = conn.execute("INSERT INTO learning_events(user_id,event_type,item,result) VALUES(?,?,?,?)", (user_id, event_type, item, result))
            row = conn.execute("SELECT * FROM learning_events WHERE id=?", (cursor.lastrowid,)).fetchone()
        if row is None:
            raise RuntimeError("inserted learning event could not be read")
        return LearningEvent(**dict(row))

    def list_events(self, user_id: str, limit: int = 20) -> list[LearningEvent]:
        # Reuse 02's bounded limit and deterministic recent-history query.
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM learning_events WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [LearningEvent(**dict(row)) for row in rows]
