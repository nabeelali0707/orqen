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
    Status,
    Step,
    Task,
    Tool,
    ToolRegistry,
    TransientToolError,
    WorkflowRunner,
)


def fixture(*, write=False, permissions=frozenset(), confirmation=False, fail=False):
    calls = []

    async def read():
        calls.append("read")
        return {"route": "priority", "private": "customer-secret"}

    async def act(route):
        calls.append(route)
        if fail:
            raise TransientToolError("Uncertain write")
        return route

    registry = ToolRegistry(
        (
            Tool(
                "read",
                "Inspect",
                "read",
                read,
                {"type": "object", "additionalProperties": False},
                {"type": "object"},
                read_only=True,
            ),
            Tool(
                "act",
                "Route",
                "act",
                act,
                {
                    "type": "object",
                    "properties": {"route": {"type": "string"}},
                    "required": ["route"],
                    "additionalProperties": False,
                },
                {"type": "string"},
                read_only=not write,
                permissions=permissions,
                requires_confirmation=confirmation,
            ),
        )
    )

    def choose(observations):
        if not observations:
            return Task(
                "Inspect",
                lambda o: o["inspection"]["route"] == "priority",
                Plan((Step("inspection", "read"),)),
            )
        if len(observations) == 1:
            route = observations[0]["inspection"]["route"]
            return Task(
                "Route",
                lambda o: o["action"] == "priority",
                Plan((Step("action", "act", {"route": route}),)),
            )
        return None

    def verify(observations):
        return len(observations) == 2 and observations[1] == {"action": "priority"}

    return WorkflowRunner(Orchestrator(registry)), choose, verify, calls


def test_observed_result_selects_next_task_and_trace_omits_data():
    runner, choose, verify, calls = fixture()
    result = asyncio.run(runner.run(choose, verify))
    assert result.verified and calls == ["read", "priority"]
    trace = result.trace()
    assert trace["calls"] == 2 and trace["planner_calls"] == 0
    assert "customer-secret" not in json.dumps(trace)
    assert "outputs" not in json.dumps(trace)


@pytest.mark.parametrize("setting", [{"max_calls": 1}, {"max_steps": 1}])
def test_budget_is_shared_across_stages(setting):
    runner, choose, verify, calls = fixture()
    result = asyncio.run(runner.run(choose, verify, budget=Budget(**setting)))
    assert result.failure == Failure.BUDGET and calls == ["read"]


@pytest.mark.parametrize("confirmation", [False, True])
def test_dynamic_stage_cannot_bypass_permissions_or_confirmation(confirmation):
    runner, choose, verify, calls = fixture(
        write=True, permissions=frozenset({"write"}), confirmation=confirmation
    )
    access = Access(permissions={"write"}) if confirmation else Access()
    result = asyncio.run(runner.run(choose, verify, access=access))
    assert result.failure == (Failure.CONFIRMATION if confirmation else Failure.PERMISSION)
    assert calls == ["read"]


def test_uncertain_write_stops_selection_and_is_never_retried():
    runner, choose, verify, calls = fixture(write=True, fail=True)
    selections = []

    def tracked(observations):
        selections.append(len(observations))
        return choose(observations)

    result = asyncio.run(runner.run(tracked, verify))
    assert result.status == Status.UNKNOWN and result.requires_reconciliation
    assert selections == [0, 1] and calls == ["read", "priority"]


def test_final_verifier_is_independent_of_successful_stages():
    runner, choose, _, _ = fixture(write=True)
    result = asyncio.run(runner.run(choose, lambda _: False))
    assert result.status == Status.FAILED and result.requires_reconciliation
    assert all(stage.verified for stage in result.stages)


def test_selection_gets_defensive_copies():
    runner, choose, verify, _ = fixture()

    def mutate(observations):
        task = choose(observations)
        if observations:
            observations[0]["inspection"]["route"] = "corrupted"
        return task

    result = asyncio.run(runner.run(mutate, verify))
    assert result.verified
    assert result.stages[0].outputs["inspection"]["route"] == "priority"


def test_stage_limit_bounds_repeated_direct_tasks():
    runner, _, _, _ = fixture()
    task = Task("Direct", lambda _: True, Plan(direct_result=1))
    result = asyncio.run(runner.run(lambda _: task, lambda _: True, max_stages=2))
    assert result.failure == Failure.BUDGET and len(result.stages) == 2


def test_planner_call_budget_is_shared():
    runner, choose, verify, calls = fixture()

    class Planner:
        async def plan(self, goal, catalog):
            return Plan((Step("inspection", "read"),))

    runner.orchestrator.planner = Planner()
    task = replace(choose(()), plan=None)
    result = asyncio.run(runner.run(lambda _: task, verify, budget=Budget(max_planner_calls=1)))
    assert result.failure == Failure.BUDGET and calls == ["read"]
    assert result.trace()["planner_calls"] == 1


def test_async_selection_and_final_verification():
    runner, choose, verify, _ = fixture()

    async def select(observations):
        return choose(observations)

    async def check(observations):
        return verify(observations)

    assert asyncio.run(runner.run(select, check)).verified


def test_selector_timeout_is_bounded():
    runner, _, _, calls = fixture()

    async def slow(_):
        await asyncio.sleep(1)

    result = asyncio.run(runner.run(slow, lambda _: True, budget=Budget(timeout_seconds=0.01)))
    assert result.failure == Failure.BUDGET and calls == []


def test_selection_error_after_write_requires_reconciliation():
    runner, choose, verify, _ = fixture(write=True)

    def broken(observations):
        if len(observations) == 2:
            raise RuntimeError("private error")
        return choose(observations)

    result = asyncio.run(runner.run(broken, verify))
    assert result.status == Status.UNKNOWN and result.requires_reconciliation
    assert "private error" not in json.dumps(result.trace())


def test_failed_stage_is_not_supplied_to_selector():
    runner, choose, verify, calls = fixture()
    task = replace(choose(()), verify=lambda _: False)
    result = asyncio.run(runner.run(lambda _: task, verify))
    assert result.failure == Failure.VERIFICATION and len(result.stages) == 1
    assert calls == ["read"]


@pytest.mark.parametrize("value", [0, -1, True, 1001])
def test_invalid_stage_limit(value):
    runner, choose, verify, _ = fixture()
    with pytest.raises(ValueError):
        asyncio.run(runner.run(choose, verify, max_stages=value))
