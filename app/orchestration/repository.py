"""Private SQLite persistence for M08-owned orchestration state."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .contracts import Orchestration, OrchestrationStatus, OrchestrationStep, StepStatus


class OrchestrationRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS orchestrations (
                orchestration_id TEXT PRIMARY KEY, actor_user_id TEXT NOT NULL,
                session_id TEXT NOT NULL, intent TEXT NOT NULL, status TEXT NOT NULL,
                original_input TEXT NOT NULL, proposal TEXT, missing_fields_json TEXT NOT NULL,
                result_reference TEXT, error_code TEXT, recoverable INTEGER NOT NULL,
                confirmation_key TEXT, revision INTEGER NOT NULL DEFAULT 1,
                route_confidence REAL NOT NULL, route_reason TEXT NOT NULL,
                route_query TEXT, mixed_sources INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS orchestration_steps (
                step_id TEXT NOT NULL, orchestration_id TEXT NOT NULL,
                action_type TEXT NOT NULL, owner_module TEXT NOT NULL,
                command_or_query TEXT NOT NULL, parameters_json TEXT NOT NULL,
                depends_on_json TEXT NOT NULL, status TEXT NOT NULL,
                result_reference TEXT, error_code TEXT, order_index INTEGER NOT NULL,
                PRIMARY KEY(orchestration_id, step_id),
                FOREIGN KEY(orchestration_id) REFERENCES orchestrations(orchestration_id))""")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _dto(row: sqlite3.Row) -> Orchestration:
        return Orchestration(
            orchestration_id=row["orchestration_id"], actor_user_id=row["actor_user_id"],
            session_id=row["session_id"], intent=row["intent"],
            status=OrchestrationStatus(row["status"]), original_input=row["original_input"],
            proposal=row["proposal"], missing_fields=tuple(json.loads(row["missing_fields_json"])),
            confirmation_key=row["confirmation_key"],
            result_reference=row["result_reference"], error_code=row["error_code"],
            recoverable=bool(row["recoverable"]), revision=int(row["revision"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def insert(self, values: dict) -> Orchestration:
        with self._connect() as conn:
            conn.execute("""INSERT INTO orchestrations(orchestration_id,actor_user_id,session_id,intent,status,
                original_input,missing_fields_json,recoverable,route_confidence,route_reason,route_query,mixed_sources)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
                values["orchestration_id"], values["actor_user_id"], values["session_id"], values["intent"],
                values["status"], values["original_input"], json.dumps(values["missing_fields"]), 1,
                values["route_confidence"], values["route_reason"], values["route_query"], values["mixed_sources"],
            ))
            row = conn.execute("SELECT * FROM orchestrations WHERE orchestration_id=?", (values["orchestration_id"],)).fetchone()
        return self._dto(row)

    def get(self, actor_user_id: str, orchestration_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM orchestrations WHERE actor_user_id=? AND orchestration_id=?",
                                (actor_user_id, orchestration_id)).fetchone()

    def pending(self, actor_user_id: str, session_id: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("""SELECT * FROM orchestrations WHERE actor_user_id=? AND session_id=?
                AND status IN ('NEEDS_CLARIFICATION','READY','AWAITING_CONFIRMATION','EXECUTING','UNCERTAIN') ORDER BY created_at DESC""",
                (actor_user_id, session_id)).fetchall()

    def latest(self, actor_user_id: str, session_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("""SELECT * FROM orchestrations WHERE actor_user_id=? AND session_id=?
                ORDER BY rowid DESC LIMIT 1""", (actor_user_id, session_id)).fetchone()

    def recover_executing(self) -> int:
        """Mark persisted in-flight work unknown during single-process app startup."""
        with self._connect() as conn:
            cur = conn.execute("""UPDATE orchestrations SET status='UNCERTAIN',
                error_code='PROCESS_INTERRUPTED', recoverable=0,
                revision=revision+1, updated_at=CURRENT_TIMESTAMP
                WHERE status='EXECUTING'""")
            conn.execute("UPDATE orchestration_steps SET status='UNCERTAIN', error_code='PROCESS_INTERRUPTED' WHERE status='RUNNING'")
            return cur.rowcount

    def replace_steps(self, orchestration_id: str, steps: list[dict]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM orchestration_steps WHERE orchestration_id=?", (orchestration_id,))
            conn.executemany("""INSERT INTO orchestration_steps(
                orchestration_id,step_id,action_type,owner_module,command_or_query,parameters_json,
                depends_on_json,status,order_index) VALUES(?,?,?,?,?,?,?,?,?)""",
                [(orchestration_id, step["step_id"], step["action_type"], step["owner_module"],
                  step["command_or_query"], json.dumps(step["parameters"], ensure_ascii=False, sort_keys=True),
                  json.dumps(step["depends_on"]), "PENDING", index)
                 for index, step in enumerate(steps)])

    def steps(self, orchestration_id: str) -> tuple[OrchestrationStep, ...]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM orchestration_steps WHERE orchestration_id=? ORDER BY order_index",
                                (orchestration_id,)).fetchall()
        return tuple(OrchestrationStep(
            row["step_id"], row["action_type"], row["owner_module"], row["command_or_query"],
            row["parameters_json"], tuple(json.loads(row["depends_on_json"])), StepStatus(row["status"]),
            row["result_reference"], row["error_code"], int(row["order_index"])) for row in rows)

    def update_step(self, orchestration_id: str, step_id: str, *, expected: tuple[str, ...], status: str,
                    result_reference: str | None = None, error_code: str | None = None) -> None:
        with self._connect() as conn:
            slots = ",".join("?" for _ in expected)
            cursor = conn.execute(f"""UPDATE orchestration_steps SET status=?,result_reference=?,error_code=?
                WHERE orchestration_id=? AND step_id=? AND status IN ({slots})""",
                (status, result_reference, error_code, orchestration_id, step_id, *expected))
            if cursor.rowcount != 1:
                raise ValueError("step state changed or is no longer executable")

    def update(self, actor_user_id: str, orchestration_id: str, *, expected: tuple[str, ...],
               status: str, proposal: str | None = None, missing_fields: tuple[str, ...] | None = None,
               confirmation_key: str | None = None, error_code: str | None = None,
               result_reference: str | None = None, recoverable: bool = True,
               steps: list[dict] | None = None) -> sqlite3.Row:
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in expected)
            cur = conn.execute(f"""UPDATE orchestrations SET status=?, proposal=?,
                missing_fields_json=COALESCE(?,missing_fields_json), confirmation_key=?, error_code=?,
                result_reference=?, recoverable=?, revision=revision+1, updated_at=CURRENT_TIMESTAMP
                WHERE actor_user_id=? AND orchestration_id=? AND status IN ({placeholders})""",
                (status, proposal, json.dumps(missing_fields) if missing_fields is not None else None,
                 confirmation_key, error_code, result_reference, int(recoverable), actor_user_id,
                 orchestration_id, *expected))
            if cur.rowcount != 1:
                raise ValueError("invalid orchestration transition or operation is no longer pending")
            if steps is not None:
                conn.execute("DELETE FROM orchestration_steps WHERE orchestration_id=?", (orchestration_id,))
                conn.executemany("""INSERT INTO orchestration_steps(
                    orchestration_id,step_id,action_type,owner_module,command_or_query,parameters_json,
                    depends_on_json,status,order_index) VALUES(?,?,?,?,?,?,?,?,?)""",
                    [(orchestration_id, step["step_id"], step["action_type"], step["owner_module"],
                      step["command_or_query"], json.dumps(step["parameters"], ensure_ascii=False, sort_keys=True),
                      json.dumps(step["depends_on"]), "PENDING", index)
                     for index, step in enumerate(steps)])
            row = conn.execute("SELECT * FROM orchestrations WHERE orchestration_id=?", (orchestration_id,)).fetchone()
        return row
