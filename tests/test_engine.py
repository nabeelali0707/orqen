import asyncio
import json
from dataclasses import replace

import pytest

from orqen import (
    Access,
    Budget,
    Failure,
    Orchestrator,
    Plan,
    Ref,
    Status,
    Step,
    Strategy,
    Task,
    Tool,
    ToolRegistry,
    TransientToolError,
)

INPUT = {
    "type": "object",
    "properties": {"value": {"type": "integer"}},
    "required": ["value"],
    "additionalProperties": False,
}
OUTPUT = {"type": "integer"}


async def double(value):
    return value * 2


def make_tool(**kwargs):
    return replace(
        Tool("double", "Double a number", "math.double", double, INPUT, OUTPUT, read_only=True),
        **kwargs,
    )


def task(*steps, verify=lambda out: out.get("a") == 4, strategy=None):
    return Task("Double a value", verify, Plan(tuple(steps), strategy=strategy))


def run(request, tools=None, **kwargs):
    engine = Orchestrator(ToolRegistry(tuple(tools or [make_tool()])))
    return asyncio.run(engine.run(request, **kwargs))


def test_single_call_is_verified():
    result = run(task(Step("a", "math.double", {"value": 2})))
    assert result.status == Status.SUCCESS
    assert result.outputs == {"a": 4}
    assert result.calls == 1 and result.verified
    assert result.strategy == Strategy.FUNCTION


def test_direct_response_has_no_tool_calls():
    result = run(Task("Hello", lambda out: out["direct"] == "Hello!", Plan(direct_result="Hello!")))
    assert result.status == Status.SUCCESS and result.calls == 0
    assert result.strategy == Strategy.DIRECT


def test_dependencies_are_sorted_and_references_are_resolved():
    result = run(
        task(
            Step("b", "math.double", {"value": Ref("a")}),
            Step("a", "math.double", {"value": 2}),
            verify=lambda out: out == {"a": 4, "b": 8},
        )
    )
    assert result.status == Status.SUCCESS
    assert result.strategy == Strategy.PLAN
    assert [event.step for event in result.events if event.kind == "called"] == ["a", "b"]


@pytest.mark.parametrize(
    "steps",
    [
        (Step("a", "math.double", {"value": Ref("missing")}),),
        (
            Step("a", "math.double", {"value": Ref("b")}),
            Step("b", "math.double", {"value": Ref("a")}),
        ),
        (Step("a", "math.double"), Step("a", "math.double")),
        (Step("direct", "math.double"),),
    ],
)
def test_invalid_graph_is_rejected_before_execution(steps):
    result = run(task(*steps))
    assert result.failure == Failure.PLAN and result.calls == 0


@pytest.mark.parametrize(
    "arguments", [{}, {"value": "2"}, {"value": True}, {"value": 2, "extra": 1}]
)
def test_invalid_arguments_never_reach_handler(arguments):
    result = run(task(Step("a", "math.double", arguments)))
    assert result.failure == Failure.ARGUMENTS and result.calls == 0


def test_permissions_and_confirmations_are_independent():
    tool = make_tool(
        permissions=frozenset({"math:write"}), read_only=False, requires_confirmation=True
    )
    request = task(Step("a", "math.double", {"value": 2}))
    assert run(request, [tool]).failure == Failure.PERMISSION
    access = Access(frozenset({"math:write"}))
    assert run(request, [tool], access=access).failure == Failure.CONFIRMATION
    access = replace(access, confirmed_tools=frozenset({"double"}))
    assert run(request, [tool], access=access).status == Status.SUCCESS


def test_wrong_output_is_failure_even_if_verifier_would_accept():
    async def wrong(value):
        return "4"

    result = run(
        task(Step("a", "math.double", {"value": 2}), verify=lambda _: True),
        [make_tool(handler=wrong)],
    )
    assert result.failure == Failure.OUTPUT and not result.verified


def test_business_condition_can_fail_on_schema_valid_output():
    result = run(task(Step("a", "math.double", {"value": 3})))
    assert result.failure == Failure.VERIFICATION
    assert result.outputs == {"a": 6}


def test_read_retries_transient_failure():
    attempts = 0

    async def flaky(value):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TransientToolError("private service details")
        return value * 2

    result = run(task(Step("a", "math.double", {"value": 2})), [make_tool(handler=flaky)])
    assert result.status == Status.SUCCESS
    assert result.calls == 2 and result.retries == 1
    assert "private service details" not in json.dumps(result.trace())


@pytest.mark.parametrize("exception", [TransientToolError, TimeoutError, RuntimeError])
def test_uncertain_writes_are_never_replayed(exception):
    writes = []

    async def write(value):
        writes.append(value)
        raise exception("response lost after commit")

    result = run(
        task(Step("a", "math.double", {"value": 2})), [make_tool(handler=write, read_only=False)]
    )
    assert result.status == Status.UNKNOWN and writes == [2]
    assert result.calls == 1 and result.retries == 0


def test_retry_limit_is_enforced():
    async def failing(value):
        raise TransientToolError()

    result = run(
        task(Step("a", "math.double", {"value": 2})),
        [make_tool(handler=failing)],
        budget=Budget(max_retries=2),
    )
    assert result.calls == 3 and result.retries == 2
    assert result.failure == Failure.TRANSIENT


def test_call_budget_also_caps_retries():
    async def failing(value):
        raise TransientToolError()

    result = run(
        task(Step("a", "math.double", {"value": 2})),
        [make_tool(handler=failing)],
        budget=Budget(max_calls=1, max_retries=5),
    )
    assert result.calls == 1 and result.failure == Failure.BUDGET


def test_tool_timeout_cancels_cooperative_handler():
    cancelled = []

    async def slow(value):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.append(True)

    result = run(
        task(Step("a", "math.double", {"value": 2})),
        [make_tool(handler=slow, timeout_seconds=0.01)],
        budget=Budget(max_retries=0),
    )
    assert result.failure == Failure.TIMEOUT and cancelled == [True]


def test_no_fallback_around_permission_denial():
    result = run(
        task(Step("a", "math.double", {"value": 2})),
        [
            make_tool(name="a_private", permissions=frozenset({"secret"})),
            make_tool(name="b_public"),
        ],
    )
    assert result.failure == Failure.PERMISSION and result.calls == 0


def test_unavailable_tool_can_fall_back_within_capability():
    result = run(
        task(Step("a", "math.double", {"value": 2})),
        [
            make_tool(name="a_offline", available=False),
            make_tool(name="b_backup"),
        ],
    )
    assert result.status == Status.SUCCESS
    assert any(event.kind == "fallback" for event in result.events)


def test_explicit_tool_pin_is_respected():
    result = run(
        task(Step("a", "math.double", {"value": 2}, tool="offline")),
        [
            make_tool(name="offline", available=False),
            make_tool(name="backup"),
        ],
    )
    assert result.failure == Failure.UNAVAILABLE and result.calls == 0


def test_unknown_capability_never_routes_by_keyword_alone():
    result = run(task(Step("a", "unrelated", {"value": 2}, query="Double a number")))
    assert result.failure == Failure.NO_TOOL


def test_unsupported_multi_agent_does_not_execute():
    result = run(task(Step("a", "math.double", {"value": 2}), strategy=Strategy.MULTI_AGENT))
    assert result.failure == Failure.UNSUPPORTED and result.calls == 0


def test_trace_excludes_inputs_outputs_and_goal():
    result = run(Task("PRIVATE_GOAL", lambda out: True, Plan(direct_result="SECRET_RESULT")))
    trace = json.dumps(result.trace())
    assert "PRIVATE_GOAL" not in trace and "SECRET_RESULT" not in trace
    assert result.estimated_cost is None


def test_planner_receives_only_authorized_metadata():
    class FakePlanner:
        async def plan(self, goal, catalog):
            assert goal == "Double a value"
            assert [tool["name"] for tool in catalog] == ["double"]
            assert "handler" not in catalog[0]
            return Plan((Step("a", "math.double", {"value": 2}),))

    engine = Orchestrator(
        ToolRegistry((make_tool(), make_tool(name="private", permissions=frozenset({"private"})))),
        planner=FakePlanner(),
    )
    result = asyncio.run(engine.run(Task("Double a value", lambda out: out["a"] == 4)))
    assert result.status == Status.SUCCESS


def test_planner_cannot_grant_permissions_by_naming_hidden_tool():
    class BadPlanner:
        async def plan(self, goal, catalog):
            return Plan((Step("a", "math.double", {"value": 2}, tool="private"),))

    engine = Orchestrator(
        ToolRegistry((make_tool(name="private", permissions=frozenset({"p"})),)),
        planner=BadPlanner(),
    )
    result = asyncio.run(engine.run(Task("Do something", lambda _: True)))
    assert result.failure == Failure.PERMISSION and result.calls == 0


def test_async_verifier_can_check_independent_state():
    async def verify(outputs):
        await asyncio.sleep(0)
        return outputs["a"] == 4

    assert run(task(Step("a", "math.double", {"value": 2}), verify=verify)).verified


def test_verifier_requires_literal_true():
    result = run(task(Step("a", "math.double", {"value": 2}), verify=lambda _: {"error": True}))
    assert result.failure == Failure.VERIFICATION


def test_zero_call_budget_still_allows_direct_response():
    result = run(Task("Answer", lambda _: True, Plan(direct_result=1)), budget=Budget(max_calls=0))
    assert result.verified and result.calls == 0


def test_partial_results_are_retained_when_later_call_is_blocked():
    result = run(
        task(Step("a", "math.double", {"value": 2}), Step("b", "missing", {}, depends_on=("a",)))
    )
    assert result.outputs == {"a": 4} and result.failure == Failure.NO_TOOL
