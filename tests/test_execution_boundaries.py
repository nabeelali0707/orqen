import asyncio
from dataclasses import replace

import pytest
from test_engine import make_tool, run, task

from orqen import Budget, Failure, Ref, Status, Step


@pytest.mark.parametrize(
    "defect,expected",
    [
        ("permission", Failure.PERMISSION),
        ("confirmation", Failure.CONFIRMATION),
        ("arguments", Failure.ARGUMENTS),
        ("missing", Failure.NO_TOOL),
        ("budget", Failure.BUDGET),
    ],
)
def test_known_later_failure_prevents_earlier_write(defect, expected):
    ledger = []

    async def write(value):
        ledger.append(value)
        return value * 2

    first = make_tool(name="write", capability="write", handler=write, read_only=False)
    second = make_tool()
    arguments = {"value": 2}
    capability = "math.double"
    budget = Budget(max_calls=1 if defect == "budget" else 12)
    if defect == "permission":
        second = replace(second, permissions=frozenset({"private"}))
    elif defect == "confirmation":
        second = replace(second, requires_confirmation=True)
    elif defect == "arguments":
        arguments = {"value": "invalid"}
    elif defect == "missing":
        capability = "missing"
    result = run(
        task(Step("a", "write", {"value": 2}), Step("b", capability, arguments, depends_on=("a",))),
        [first, second],
        budget=budget,
    )
    assert result.failure == expected
    assert ledger == [] and result.calls == 0


def test_verifier_exception_after_write_is_unknown_not_failed():
    ledger = []

    async def write(value):
        ledger.append(value)
        return value * 2

    def unavailable_verifier(outputs):
        raise ConnectionError("PRIVATE_STATE_ENDPOINT")

    result = run(
        task(Step("a", "math.double", {"value": 2}), verify=unavailable_verifier),
        [make_tool(handler=write, read_only=False)],
    )
    assert ledger == [2]
    assert result.status == Status.UNKNOWN and result.failure == Failure.VERIFICATION


def test_verifier_timeout_after_write_is_unknown():
    async def unavailable_verifier(outputs):
        await asyncio.sleep(1)
        return True

    result = run(
        task(Step("a", "math.double", {"value": 2}), verify=unavailable_verifier),
        [make_tool(read_only=False)],
        budget=Budget(timeout_seconds=0.02),
    )
    assert result.status == Status.UNKNOWN and result.failure == Failure.BUDGET


def test_dynamic_later_failure_retains_outputs_and_write_metadata():
    result = run(
        task(Step("a", "math.double", {"value": 2}), Step("b", "other", {"value": Ref("a")})),
        [
            make_tool(read_only=False),
            make_tool(name="other", capability="other", precondition=lambda a, c: False),
        ],
    )
    assert result.failure == Failure.PRECONDITION and result.outputs == {"a": 4}
    assert result.write_steps == ("a",)
    assert result.requires_reconciliation
    assert result.trace()["write_steps"] == ["a"]


def test_false_verifier_after_write_is_known_goal_failure_but_not_safe_replay():
    result = run(
        task(Step("a", "math.double", {"value": 2}), verify=lambda _: False),
        [make_tool(read_only=False)],
    )
    assert result.status == Status.FAILED
    assert result.requires_reconciliation


def test_verified_write_has_recorded_attempt_but_no_reconciliation_flag():
    result = run(task(Step("a", "math.double", {"value": 2})), [make_tool(read_only=False)])
    assert result.verified and result.write_steps == ("a",)
    assert not result.requires_reconciliation
