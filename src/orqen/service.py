"""Application-owned task registration and durable, metadata-only execution history."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .engine import Orchestrator
from .models import Access, Budget, Plan, Step, Task, Tool
from .registry import ResultValidator, ToolRegistry


@dataclass(frozen=True)
class RegisteredTask:
    name: str
    description: str
    input_schema: dict
    build: Callable[[dict], tuple[Orchestrator, Task]]
    permissions: frozenset[str] = frozenset()
    budget: Budget = Budget()


class ServiceError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


class ExecutionService:
    """Single-process service. Restart never replays pending/uncertain operations.

    A registered builder is trusted application code. Clients cannot register tools,
    supply Python, grant permissions, change budgets, or replace task verification.
    """

    def __init__(self, tasks: tuple[RegisteredTask, ...], database: Path, *, max_runs=10000):
        self.tasks = {task.name: task for task in tasks}
        if len(self.tasks) != len(tasks):
            raise ValueError("Duplicate registered task")
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.max_runs = max_runs
        self.active = 0
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL, task TEXT NOT NULL, created TEXT NOT NULL,
                status TEXT NOT NULL, trace TEXT, UNIQUE(owner, request_key))""")
            connection.execute("UPDATE runs SET status='unknown' WHERE status='running'")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def catalog(self, permissions: frozenset[str]) -> list[dict]:
        return [
            {"name": task.name, "description": task.description, "input_schema": task.input_schema}
            for task in self.tasks.values()
            if task.permissions <= permissions
        ]

    def history(self, owner: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, task, created, status, trace FROM runs WHERE owner=? "
                "ORDER BY created DESC LIMIT 100",
                (owner,),
            ).fetchall()
        return [self._row(row) for row in rows]

    def get(self, owner: str, run_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, task, created, status, trace FROM runs WHERE owner=? AND id=?",
                (owner, run_id),
            ).fetchone()
        if row is None:
            raise ServiceError(404, "Run not found")
        return self._row(row)

    @staticmethod
    def _row(row) -> dict:
        return {
            "id": row[0],
            "task": row[1],
            "created": row[2],
            "status": row[3],
            "trace": json.loads(row[4]) if row[4] else None,
            "requires_reconciliation": row[3] == "unknown"
            or bool(row[4] and json.loads(row[4]).get("requires_reconciliation")),
        }

    async def execute(
        self, owner: str, permissions: frozenset[str], name: str, inputs: dict, request_key: str
    ) -> dict:
        if type(request_key) is not str or not 1 <= len(request_key) <= 128:
            raise ServiceError(400, "An idempotency key of 1-128 characters is required")
        task = self.tasks.get(name)
        if task is None or not task.permissions <= permissions:
            raise ServiceError(404, "Task not found")
        if not ResultValidator.matches(task.input_schema, inputs):
            raise ServiceError(400, "Inputs do not match the registered task schema")
        encoded = json.dumps([name, inputs], sort_keys=True, allow_nan=False).encode()
        if len(encoded) > 16384:
            raise ServiceError(413, "Request too large")
        fingerprint = hashlib.sha256(encoded).hexdigest()
        run_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT id, fingerprint FROM runs WHERE owner=? AND request_key=?",
                (owner, request_key),
            ).fetchone()
            if existing:
                if existing[1] != fingerprint:
                    raise ServiceError(409, "Idempotency key already used for a different request")
                return self.get(owner, existing[0])
            if self.active >= 4:
                raise ServiceError(503, "Execution capacity reached")
            if connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] >= self.max_runs:
                raise ServiceError(503, "History capacity reached; operator maintenance required")
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                (
                    run_id,
                    owner,
                    request_key,
                    fingerprint,
                    name,
                    datetime.now(UTC).isoformat(),
                    "running",
                ),
            )
        self.active += 1
        try:
            engine, specification = task.build(inputs)
            result = await engine.run(specification, access=Access(permissions), budget=task.budget)
            with self._connect() as connection:
                connection.execute(
                    "UPDATE runs SET status=?, trace=? WHERE id=?",
                    (result.status.value, json.dumps(result.trace()), run_id),
                )
        except BaseException:
            with self._connect() as connection:
                connection.execute("UPDATE runs SET status='unknown' WHERE id=?", (run_id,))
            raise
        finally:
            self.active -= 1
        return self.get(owner, run_id)


def demo_service(database: Path) -> ExecutionService:
    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "integer", "minimum": -1000000, "maximum": 1000000},
            "b": {"type": "integer", "minimum": -1000000, "maximum": 1000000},
        },
        "required": ["a", "b"],
        "additionalProperties": False,
    }

    def build(inputs):
        async def add(a, b):
            await asyncio.sleep(0)
            return a + b

        tool = Tool("add", "Add integers", "add", add, schema, {"type": "integer"}, read_only=True)
        return Orchestrator(ToolRegistry((tool,))), Task(
            "Registered addition",
            lambda out: out == {"sum": inputs["a"] + inputs["b"]},
            Plan((Step("sum", "add", inputs),)),
        )

    return ExecutionService(
        (
            RegisteredTask(
                "addition",
                "Verified integer addition",
                schema,
                build,
                budget=Budget(max_calls=1, max_steps=1),
            ),
        ),
        database,
    )
