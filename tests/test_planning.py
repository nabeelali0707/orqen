import asyncio
import json

import pytest
from test_engine import make_tool

from orqen import (
    Budget,
    CatalogPolicy,
    Failure,
    JSONPlanner,
    Orchestrator,
    Plan,
    Status,
    Step,
    Task,
    ToolRegistry,
)


def response(*steps):
    return json.dumps({"kind": "tools", "steps": list(steps)})


def step(id="result", tool="double", arguments=None):
    return {
        "id": id,
        "tool": tool,
        "arguments": arguments if arguments is not None else {"value": {"literal": 2}},
        "depends_on": [],
    }


def execute(raw, *, tools=None, budget=None, policy=None):
    async def generate(request):
        return raw

    engine = Orchestrator(
        ToolRegistry(tuple(tools or [make_tool()])),
        planner=JSONPlanner(generate),
        catalog_policy=policy,
    )
    return asyncio.run(
        engine.run(Task("Double a number", lambda out: out["result"] == 4), budget=budget)
    )


def test_json_generation_runs_through_contract_executor():
    result = execute(response(step()))
    assert result.status == Status.SUCCESS and result.planner_calls == 1
    assert result.calls == 1 and result.trace()["planner_calls"] == 1


def test_reference_plan_is_decoded_and_ordered():
    result = execute(
        response(
            step("result", arguments={"value": {"ref": {"step": "first", "path": []}}}),
            step("first", arguments={"value": {"literal": 1}}),
        )
    )
    assert result.verified and result.outputs == {"first": 2, "result": 4}


@pytest.mark.parametrize(
    "raw",
    [
        '```json\n{"kind":"direct","result":4}\n```',
        '{"kind":"direct","kind":"tools","result":4}',
        '{"kind":"direct","result":NaN}',
        '{"kind":"direct","result":Infinity}',
        '{"kind":"direct","result":4,"permissions":["admin"]}',
        response(step(tool="invented")),
        response(step(arguments={"value": {"literal": "2"}})),
        response(step(arguments={"value": {"ref": {"step": "result", "path": []}}})),
        response(step(arguments={"value": {"literal": 2, "ref": {"step": "x", "path": []}}})),
    ],
)
def test_invalid_generated_plan_is_rejected_before_any_calls(raw):
    result = execute(raw)
    assert result.failure == Failure.PLAN and result.calls == 0


def test_invalid_later_literal_is_caught_before_earlier_write():
    writes = []

    async def write(value):
        writes.append(value)
        return value * 2

    result = execute(
        response(step("first"), step(arguments={"value": {"literal": "bad"}})),
        tools=[make_tool(handler=write, read_only=False)],
    )
    assert result.failure == Failure.PLAN and not writes


def test_transport_cannot_mutate_catalog_to_authorize_another_tool():
    async def generate(request):
        request.catalog[0]["name"] = "invented"
        return response(step(tool="invented"))

    engine = Orchestrator(ToolRegistry((make_tool(),)), planner=JSONPlanner(generate))
    result = asyncio.run(engine.run(Task("Double", lambda _: True)))
    assert result.failure == Failure.PLAN and result.calls == 0


def test_literal_reference_shaped_objects_are_not_interpreted():
    async def generate(request):
        return response(step(arguments={"value": {"literal": {"ref": {"step": "missing"}}}}))

    catalog = ({"name": "double", "capability": "echo", "input_schema": {"type": "object"}},)
    plan = asyncio.run(JSONPlanner(generate).plan("Echo", catalog))
    assert plan.steps[0].arguments == {"value": {"ref": {"step": "missing"}}}


def test_response_size_limit_is_enforced():
    async def generate(request):
        return json.dumps({"kind": "direct", "result": "x" * 100})

    with pytest.raises(ValueError, match="bounded"):
        asyncio.run(JSONPlanner(generate, max_response_bytes=30).plan("Answer", ()))


def test_expansion_is_bounded_and_happens_before_execution():
    catalogs = []

    async def generate(request):
        catalogs.append([tool["name"] for tool in request.catalog])
        if len(request.catalog) == 1:
            return '{"kind":"expand_catalog"}'
        return response(step(tool="backup"))

    tools = (make_tool(), make_tool(name="backup", description="Alternative"))
    engine = Orchestrator(
        ToolRegistry(tools), planner=JSONPlanner(generate), catalog_policy=CatalogPolicy("fixed", 1)
    )
    result = asyncio.run(engine.run(Task("Double a number", lambda out: out["result"] == 4)))
    assert result.verified and result.planner_calls == 2 and result.calls == 1
    assert catalogs == [["double"], ["double", "backup"]]
    offered = [event.candidates for event in result.events if event.kind == "catalog_offered"]
    assert offered == [("double",), ("double", "backup")]


def test_zero_planning_budget_never_invokes_transport():
    result = execute(response(step()), budget=Budget(max_planner_calls=0))
    assert result.failure == Failure.BUDGET
    assert result.planner_calls == result.calls == 0


def test_no_repeated_expansion_when_all_authorized_tools_are_offered():
    result = execute('{"kind":"expand_catalog"}')
    assert result.failure == Failure.NO_TOOL and result.planner_calls == 1


def test_expansion_cannot_expose_unauthorized_tools():
    result = execute(
        response(step(tool="private")),
        tools=[
            make_tool(),
            make_tool(name="private", permissions=frozenset({"secret"})),
        ],
    )
    assert result.failure == Failure.PLAN and result.calls == 0
    assert "private" not in str(result.trace())


def test_expansion_cannot_bypass_planner_call_budget():
    result = execute(
        '{"kind":"expand_catalog"}',
        tools=[make_tool(), make_tool(name="backup")],
        policy=CatalogPolicy("fixed", 1),
        budget=Budget(max_planner_calls=1),
    )
    assert result.failure == Failure.BUDGET and result.planner_calls == 1


def test_generated_reference_plan_obeys_executor_step_budget():
    result = execute(response(step()), budget=Budget(max_steps=0))
    assert result.failure == Failure.BUDGET and result.calls == 0


def test_planner_timeout_counts_attempt_but_not_tool_call():
    async def generate(request):
        await asyncio.sleep(1)
        return response(step())

    engine = Orchestrator(ToolRegistry((make_tool(),)), planner=JSONPlanner(generate))
    result = asyncio.run(
        engine.run(Task("Double", lambda _: True), budget=Budget(timeout_seconds=0.01))
    )
    assert result.failure == Failure.BUDGET and result.planner_calls == 1 and result.calls == 0


def test_supplied_plan_does_not_spend_planner_budget():
    task = Task(
        "Double",
        lambda out: out["result"] == 4,
        Plan((Step("result", "math.double", {"value": 2}),)),
    )
    engine = Orchestrator(ToolRegistry((make_tool(),)))
    result = asyncio.run(engine.run(task, budget=Budget(max_planner_calls=0)))
    assert result.verified and result.planner_calls == 0
