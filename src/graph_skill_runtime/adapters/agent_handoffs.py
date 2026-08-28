"""Durable ownership of cooperative host-native Agent handoffs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from graph_skill_runtime.domain.models import (
    AgentResult,
    AgentTask,
    RunResult,
)


@dataclass(frozen=True)
class AgentHandoffRecord:
    """One persisted wait point and its private LangGraph location."""

    checkpoint_ref: str
    task: AgentTask
    checkpoint_id: str
    checkpoint_ns: str
    required_response: RunResult
    result_hash: str | None = None
    response: RunResult | None = None


HandoffContinuation = Callable[
    [AgentHandoffRecord, str],
    tuple[RunResult, AgentHandoffRecord | None],
]


class SqliteAgentHandoffStore:
    """Serialize submissions and cache their causally produced responses.

    This database deliberately stays separate from LangGraph's checkpoint
    database.  A handoff owns the cross-process dispatch/result protocol;
    LangGraph owns graph state.  ``FrameworkState.agent_result_hashes`` bridges
    the unavoidable crash window between those two independent owners.

    The write path borrows SQLite's documented ``BEGIN IMMEDIATE`` single-writer
    transaction and Stripe's idempotency shape: an exact retry receives the
    cached response, while content drift for the same identity is rejected.
    Unlike Stripe's time-bounded request cache, records are not pruned by age:
    a checkpoint must remain recoverable until this runtime owns an explicit
    retention lifecycle.
    """

    def __init__(self, path: Path) -> None:
        self._path = path.resolve(strict=False)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_handoffs (
                    checkpoint_ref TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL,
                    task_json TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    required_response_json TEXT NOT NULL,
                    result_json TEXT,
                    result_hash TEXT,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS agent_handoffs_run_id
                    ON agent_handoffs(run_id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @staticmethod
    def _json(model: AgentTask | AgentResult | RunResult) -> str:
        return model.model_dump_json()

    @staticmethod
    def _record(row: sqlite3.Row) -> AgentHandoffRecord:
        result_hash = row["result_hash"]
        response_json = row["response_json"]
        return AgentHandoffRecord(
            checkpoint_ref=str(row["checkpoint_ref"]),
            task=AgentTask.model_validate_json(row["task_json"]),
            checkpoint_id=str(row["checkpoint_id"]),
            checkpoint_ns=str(row["checkpoint_ns"]),
            required_response=RunResult.model_validate_json(
                row["required_response_json"]
            ),
            result_hash=str(result_hash) if result_hash is not None else None,
            response=(
                RunResult.model_validate_json(response_json)
                if response_json is not None
                else None
            ),
        )

    @staticmethod
    def _same_required(left: AgentHandoffRecord, right: AgentHandoffRecord) -> bool:
        return (
            left.checkpoint_ref == right.checkpoint_ref
            and left.task == right.task
            and left.checkpoint_id == right.checkpoint_id
            and left.checkpoint_ns == right.checkpoint_ns
            and left.required_response == right.required_response
        )

    def _insert_required(
        self,
        connection: sqlite3.Connection,
        record: AgentHandoffRecord,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        try:
            connection.execute(
                """
                INSERT INTO agent_handoffs (
                    checkpoint_ref, task_id, run_id, task_json,
                    checkpoint_id, checkpoint_ns, required_response_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.checkpoint_ref,
                    record.task.task_id,
                    record.task.run_id,
                    self._json(record.task),
                    record.checkpoint_id,
                    record.checkpoint_ns,
                    self._json(record.required_response),
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError:
            row = connection.execute(
                """
                SELECT * FROM agent_handoffs
                WHERE checkpoint_ref = ? OR task_id = ?
                """,
                (record.checkpoint_ref, record.task.task_id),
            ).fetchone()
            if row is None or not self._same_required(self._record(row), record):
                raise ValueError(
                    "AgentTask identity already exists with different durable content"
                ) from None

    def put_required(self, record: AgentHandoffRecord) -> None:
        """Make a task durable before an ``agent_required`` becomes visible."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._insert_required(connection, record)
            connection.commit()

    def load(self, checkpoint_ref: str) -> AgentHandoffRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_handoffs WHERE checkpoint_ref = ?",
                (checkpoint_ref,),
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown Agent handoff checkpoint_ref {checkpoint_ref!r}")
        return self._record(row)

    def recover_run(self, run_id: str) -> RunResult | None:
        """Return the latest externally visible result for an idempotent retry."""

        with self._connect() as connection:
            active = connection.execute(
                """
                SELECT * FROM agent_handoffs
                WHERE run_id = ? AND response_json IS NULL
                ORDER BY rowid DESC LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if active is not None:
                return self._record(active).required_response
            completed = connection.execute(
                """
                SELECT * FROM agent_handoffs
                WHERE run_id = ? AND response_json IS NOT NULL
                ORDER BY rowid DESC LIMIT 1
                """,
                (run_id,),
            ).fetchone()
        if completed is None:
            return None
        return self._record(completed).response

    def submit(
        self,
        checkpoint_ref: str,
        result: AgentResult,
        result_hash: str,
        continuation: HandoffContinuation,
    ) -> RunResult:
        """Serialize one result application and make exact retries idempotent."""

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM agent_handoffs WHERE checkpoint_ref = ?",
                (checkpoint_ref,),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"unknown Agent handoff checkpoint_ref {checkpoint_ref!r}"
                )
            record = self._record(row)
            if record.task.task_id != result.task_id:
                raise ValueError(
                    f"AgentResult task_id {result.task_id!r} does not match "
                    f"handoff task {record.task.task_id!r}"
                )
            if record.response is not None:
                if record.result_hash != result_hash:
                    raise ValueError(
                        "this AgentTask already completed with a different result"
                    )
                connection.rollback()
                return record.response

            now = datetime.now(UTC).isoformat()
            connection.execute(
                """
                UPDATE agent_handoffs
                SET result_json = ?, result_hash = ?, updated_at = ?
                WHERE checkpoint_ref = ?
                """,
                (self._json(result), result_hash, now, checkpoint_ref),
            )
            response, next_record = continuation(record, result_hash)
            if next_record is not None:
                self._insert_required(connection, next_record)
            connection.execute(
                """
                UPDATE agent_handoffs
                SET response_json = ?, updated_at = ?
                WHERE checkpoint_ref = ?
                """,
                (self._json(response), datetime.now(UTC).isoformat(), checkpoint_ref),
            )
            connection.commit()
            return response
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def canonical_agent_result_hash(result: AgentResult) -> str:
    """Hash the complete immutable result, including provenance and executor."""

    import hashlib

    canonical = json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
