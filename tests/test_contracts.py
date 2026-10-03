import asyncio
from dataclasses import replace

import pytest
from test_engine import INPUT, OUTPUT, double, make_tool, run, task

from orqen import (
    Access,
    Budget,
    Failure,
    Orchestrator,
    Plan,
    Ref,
    Status,
    Step,
    Task,
    Tool,
    ToolRegistry,
    TransientToolError,
)


def test_schema_valid_but_disallowed_write_is_prevented():
    writes = []

    async def write(value):
        writes.append(value)
        return value * 2

    tool = make_tool(
        handler=write, read_only=False, precondition=lambda args, access: args["value"] <= 10
    )
    result = run(task(Step("a", "math.double", {"value": 100})), [tool])
    assert result.failure == Failure.PRECONDITION
    assert result.calls == 0 and not writes


@pytest.mark.parametrize("check", [lambda a, c: False, lambda a, c: "allowed"])
def test_precondition_requires_true(check):
    result = run(task(Step("a", "math.double", {"value": 2})), [make_tool(precondition=check)])
    assert result.failure == Failure.PRECONDITION and result.calls == 0


def test_check_exception_fails_closed_and_is_redacted():
    def broken(args, access):
        raise RuntimeError("PRIVATE_POLICY_SECRET")

    result = run(task(Step("a", "math.double", {"value": 2})), [make_tool(precondition=broken)])
    assert result.failure == Failure.PRECONDITION
    assert "PRIVATE_POLICY_SECRET" not in str(result.trace())


def test_precondition_is_rechecked_before_retry():
    allowed = True

    async def read(value):
        nonlocal allowed
        allowed = False
        raise TransientToolError()

    tool = make_tool(handler=read, precondition=lambda args, access: allowed)
    result = run(task(Step("a", "math.double", {"value": 2})), [tool])
    assert result.failure == Failure.PRECONDITION and result.calls == 1


def test_postcondition_blocks_dependent_action():
    writes = []

    async def write(value):
        writes.append(value)
        return value

    tools = [
        make_tool(postcondition=lambda args, output: False),
        make_tool(name="write", capability="write", handler=write, read_only=False),
    ]
    result = run(
        task(Step("a", "math.double", {"value": 2}), Step("b", "write", {"value": Ref("a")})), tools
    )
    assert result.failure == Failure.POSTCONDITION and result.calls == 1
    assert not writes and result.outputs == {}


def test_unverified_write_is_unknown_and_not_retried():
    result = run(
        task(Step("a", "math.double", {"value": 2})),
        [make_tool(read_only=False, postcondition=lambda args, output: False)],
    )
    assert result.status == Status.UNKNOWN and result.calls == 1


def test_checks_cannot_mutate_executed_arguments():
    def check(args, access):
        args["value"] = 999
        return True

    result = run(task(Step("a", "math.double", {"value": 2})), [make_tool(precondition=check)])
    assert result.outputs == {"a": 4} and result.verified


def test_async_checks_can_verify_external_state():
    async def before(args, access):
        await asyncio.sleep(0)
        return "math" in access.permissions

    async def after(args, output):
        await asyncio.sleep(0)
        return output == args["value"] * 2

    result = run(
        task(Step("a", "math.double", {"value": 2})),
        [make_tool(precondition=before, postcondition=after)],
        access=Access(frozenset({"math"})),
    )
    assert result.verified


def test_check_timeout_prevents_action():
    async def slow(args, access):
        await asyncio.sleep(1)
        return True

    result = run(
        task(Step("a", "math.double", {"value": 2})),
        [make_tool(precondition=slow)],
        budget=Budget(timeout_seconds=0.01),
    )
    assert result.failure == Failure.BUDGET and result.calls == 0


def test_default_tool_is_not_assumed_read_only():
    tool = Tool("double", "Double", "math.double", double, INPUT, OUTPUT)
    assert tool.read_only is False


@pytest.mark.parametrize("name", ["read_only", "requires_confirmation", "available"])
def test_string_flags_are_rejected(name):
    with pytest.raises(TypeError, match="bool"):
        ToolRegistry((make_tool(**{name: "false"}),))


def test_access_copies_mutable_grants():
    grants = {"math"}
    access = Access(grants)
    grants.add("write")
    assert access.permissions == frozenset({"math"})


def test_external_cancellation_propagates_without_write_replay():
    calls = []

    async def scenario():
        started = asyncio.Event()

        async def write(value):
            calls.append(value)
            started.set()
            await asyncio.sleep(10)

        engine = Orchestrator(ToolRegistry((make_tool(handler=write, read_only=False),)))
        running = asyncio.create_task(engine.run(task(Step("a", "math.double", {"value": 2}))))
        await started.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running

    asyncio.run(scenario())
    assert calls == [2]


def test_strategy_override_does_not_change_execution_algorithm():
    # A regression check documenting why these labels are not research evidence.
    from orqen import Strategy

    request = Task("Answer", lambda out: out["direct"] == 4, Plan(direct_result=4))
    first = run(request)
    second = run(replace(request, plan=replace(request.plan, strategy=Strategy.PLAN)))
    assert first.outputs == second.outputs and first.calls == second.calls == 0
