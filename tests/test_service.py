import asyncio
from dataclasses import replace

import pytest

from orqen.service import ExecutionService, ServiceError, demo_service


def test_request_key_survives_restart_and_does_not_reexecute(tmp_path):
    database = tmp_path / "runs.sqlite3"
    service = demo_service(database)
    first = asyncio.run(service.execute("alice", frozenset(), "addition", {"a": 2, "b": 3}, "key"))
    service = demo_service(database)
    second = asyncio.run(service.execute("alice", frozenset(), "addition", {"a": 2, "b": 3}, "key"))
    assert first == second and first["trace"]["verified"]
    assert len(service.history("alice")) == 1
    assert not service.history("bob")
    with pytest.raises(ServiceError, match="different request"):
        asyncio.run(service.execute("alice", frozenset(), "addition", {"a": 1, "b": 3}, "key"))
    with pytest.raises(ServiceError):
        service.get("bob", first["id"])
    assert "outputs" not in first["trace"]


def test_permissions_and_input_validation_happen_before_registration(tmp_path):
    demo = demo_service(tmp_path / "demo.db")
    task = replace(demo.tasks["addition"], permissions=frozenset({"math"}))
    service = ExecutionService((task,), tmp_path / "restricted.db")
    for inputs, permissions in (
        ({"a": 2, "b": 3}, frozenset()),
        ({"a": "2", "b": 3}, frozenset({"math"})),
    ):
        with pytest.raises(ServiceError):
            asyncio.run(service.execute("a", permissions, "addition", inputs, "key"))
    assert not service.history("a")


def test_builder_failure_remains_unknown_and_same_key_cannot_replay(tmp_path):
    service = demo_service(tmp_path / "db")
    attempts = []

    def fail(inputs):
        attempts.append(1)
        raise RuntimeError("private details")

    service.tasks["addition"] = replace(service.tasks["addition"], build=fail)
    with pytest.raises(RuntimeError):
        asyncio.run(service.execute("a", frozenset(), "addition", {"a": 1, "b": 2}, "x"))
    row = asyncio.run(service.execute("a", frozenset(), "addition", {"a": 1, "b": 2}, "x"))
    assert row["status"] == "unknown" and row["requires_reconciliation"]
    assert len(attempts) == 1


def test_history_limit_rejects_new_work_but_allows_existing_keys(tmp_path):
    service = demo_service(tmp_path / "db")
    service.max_runs = 1
    asyncio.run(service.execute("a", frozenset(), "addition", {"a": 1, "b": 2}, "x"))
    with pytest.raises(ServiceError, match="capacity"):
        asyncio.run(service.execute("a", frozenset(), "addition", {"a": 1, "b": 2}, "y"))
    assert asyncio.run(service.execute("a", frozenset(), "addition", {"a": 1, "b": 2}, "x"))


def test_concurrent_duplicate_and_cancellation_never_replay(tmp_path):
    service = demo_service(tmp_path / "db")
    original = service.tasks["addition"].build

    async def check():
        entered, release = asyncio.Event(), asyncio.Event()

        def build(inputs):
            engine, task = original(inputs)
            original_run = engine.run

            async def delayed(*args, **kwargs):
                entered.set()
                await release.wait()
                return await original_run(*args, **kwargs)

            engine.run = delayed
            return engine, task

        service.tasks["addition"] = replace(service.tasks["addition"], build=build)
        execution = asyncio.create_task(
            service.execute("a", frozenset(), "addition", {"a": 1, "b": 2}, "x")
        )
        await entered.wait()
        duplicate = await service.execute("a", frozenset(), "addition", {"a": 1, "b": 2}, "x")
        assert duplicate["status"] == "running" and len(service.history("a")) == 1
        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution
        assert service.get("a", duplicate["id"])["status"] == "unknown"
        assert service.active == 0

    asyncio.run(check())


def test_restart_marks_interrupted_rows_unknown(tmp_path):
    database = tmp_path / "db"
    service = demo_service(database)
    result = asyncio.run(service.execute("a", frozenset(), "addition", {"a": 1, "b": 2}, "x"))
    with service._connect() as connection:
        connection.execute("UPDATE runs SET status='running', trace=NULL")
    restarted = demo_service(database)
    assert restarted.get("a", result["id"])["status"] == "unknown"
