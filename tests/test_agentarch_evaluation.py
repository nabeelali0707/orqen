import asyncio
import json

import pytest

from orqen import Budget, Tool, ToolRegistry
from orqen.agentarch_evaluation import METRICS, run_case


class Dataset:
    def cases(self):
        return ({"id": "2", "goal": "Read the record, then finish with its answer"},)

    def session(self, case_id):
        self.created = Session()
        return self.created


class Session:
    instructions = "Read before responding."

    def __init__(self):
        self.history = []
        self.grades = 0

        async def read():
            self.history.append(("read", {}))
            return "observed-answer"

        async def finish(message):
            self.history.append(("finish", {"message": message}))
            return {"message": message}

        self.registry = ToolRegistry(
            (
                Tool(
                    "read",
                    "Read record",
                    "read",
                    read,
                    {"type": "object"},
                    {"type": "string"},
                    permissions={"agentarch.mock"},
                    read_only=True,
                ),
                Tool(
                    "finish",
                    "Final answer",
                    "finish",
                    finish,
                    {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                    {"type": "object"},
                    permissions={"agentarch.mock"},
                    read_only=True,
                ),
            )
        )

    def grade(self, official):
        self.grades += 1
        return official(self.history, "PRIVATE_ORACLE_LABEL")


def grader(history, truth):
    assert truth == "PRIVATE_ORACLE_LABEL"
    success = history == [("read", {}), ("finish", {"message": "observed-answer"})]
    return {
        "correct_final_outcome": success,
        "correct_tool_order": success,
        "lenient_correct_tool_order": success,
        "percent_of_correct_tool_args": 1.0 if success else 0.0,
        "exists_hallucination": False,
        "exists_tool_repetition": False,
        "number_of_custom_tools": 1,
        "total_number_of_agent_tool_calls": len(history),
        "final_message": "PRIVATE_FINAL_MESSAGE",
        "expected_tools": "PRIVATE_ORACLE_LABEL",
    }


def step(name, tool, arguments=None, depends_on=None):
    return {"id": name, "tool": tool, "arguments": arguments or {}, "depends_on": depends_on or []}


@pytest.mark.parametrize("mode", ["whole_plan", "observed"])
def test_planning_is_separate_from_official_grading_and_raw_data_is_not_exported(mode):
    dataset = Dataset()
    requests = []

    async def generate(request):
        assert "PRIVATE_ORACLE_LABEL" not in request.goal
        assert dataset.created.grades == 0
        requests.append(request)
        if mode == "whole_plan":
            steps = [
                step("read", "read"),
                step("answer", "finish", {"message": {"ref": {"step": "read", "path": []}}}),
            ]
        elif len(requests) == 1:
            steps = [step("read", "read")]
        else:
            assert "observed-answer" in request.goal
            steps = [step("answer", "finish", {"message": {"literal": "observed-answer"}})]
        return json.dumps({"kind": "tools", "steps": steps})

    result = asyncio.run(
        run_case(
            dataset,
            "2",
            generate,
            grader,
            mode=mode,
            budget=Budget(max_calls=2, max_steps=2, max_planner_calls=2),
        )
    )
    assert result["official_strict_success"] and dataset.created.grades == 1
    assert result["trace"]["planner_calls"] == (1 if mode == "whole_plan" else 2)
    assert set(result["metrics"]) == set(METRICS)
    assert "PRIVATE" not in json.dumps(result)
    assert "observed-answer" not in json.dumps(result)


def test_budget_stops_observation_loop_and_failed_attempt_is_still_graded():
    async def generate(_):
        return json.dumps({"kind": "tools", "steps": [step("read", "read")]})

    dataset = Dataset()
    result = asyncio.run(
        run_case(
            dataset,
            "2",
            generate,
            grader,
            mode="observed",
            budget=Budget(max_calls=1, max_steps=1, max_planner_calls=1),
        )
    )
    assert result["trace"]["failure"] == "budget_exhausted"
    assert result["graded"] and not result["official_strict_success"]
    assert dataset.created.grades == 1


def test_grader_exception_is_missing_evidence_not_a_success_or_exported_error():
    async def generate(_):
        return '{"kind":"direct","result":"answer"}'

    def broken(*args):
        raise ValueError("PRIVATE ERROR")

    result = asyncio.run(
        run_case(Dataset(), "2", generate, broken, mode="whole_plan", budget=Budget())
    )
    assert not result["graded"] and result["official_strict_success"] is None
    assert "PRIVATE" not in json.dumps(result)


def test_context_limit_prevents_transport_invocation():
    async def forbidden(_):
        raise AssertionError("Transport must not run")

    result = asyncio.run(
        run_case(
            Dataset(), "2", forbidden, grader, mode="observed", budget=Budget(), max_context_bytes=1
        )
    )
    assert result["trace"]["calls"] == 0 and not result["official_strict_success"]


def test_finish_cannot_be_scheduled_before_other_tools_through_dependencies():
    async def generate(_):
        return json.dumps(
            {
                "kind": "tools",
                "steps": [
                    step("read", "read", depends_on=["answer"]),
                    step("answer", "finish", {"message": {"literal": "observed-answer"}}),
                ],
            }
        )

    result = asyncio.run(
        run_case(Dataset(), "2", generate, grader, mode="whole_plan", budget=Budget())
    )
    assert result["trace"]["calls"] == 0 and result["trace"]["failure"] == "invalid_plan"
