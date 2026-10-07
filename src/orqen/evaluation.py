"""Deterministic, stateful fault experiments. These are not LLM benchmarks."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import statistics
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from importlib.metadata import version
from pathlib import Path
from typing import Any

from .engine import Orchestrator
from .models import (
    Access,
    Budget,
    Failure,
    Plan,
    Ref,
    RunResult,
    Status,
    Step,
    Strategy,
    Task,
    Tool,
    TransientToolError,
)
from .registry import ToolRegistry


@dataclass(frozen=True)
class Configuration:
    name: str
    ranked_tools: bool
    recovery: bool


CONFIGURATIONS = (
    Configuration("fixed", False, False),
    Configuration("ranking_only", True, False),
    Configuration("recovery_only", False, True),
    Configuration("ranking_and_recovery", True, True),
)

CASE_IDS = (
    "direct",
    "single_read",
    "dependent_reads",
    "transient_read",
    "denied_write",
    "business_limit",
    "wrong_record",
    "lost_write_response",
    "false_write_ack",
)


@dataclass(frozen=True)
class Grade:
    goal_satisfied: bool
    policy_ok: bool
    expected_behavior: bool


@dataclass(frozen=True)
class Scenario:
    task: Task
    registry: ToolRegistry
    access: Access
    category: str
    grade: Callable[[RunResult], Grade]


def _scenario(case_id: str) -> Scenario:
    """New closures/state for every attempt; graders never trust result.verified."""
    calls = 0
    ledger: list[int] = []
    input_schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
        "additionalProperties": False,
    }

    async def read(value: int) -> int:
        nonlocal calls
        calls += 1
        if case_id == "transient_read" and calls == 1:
            raise TransientToolError("Injected read failure")
        return value * 2

    async def write(value: int) -> int:
        if case_id != "false_write_ack":
            ledger.append(value)
        if case_id == "lost_write_response":
            raise TimeoutError("Injected lost acknowledgement after commit")
        return value

    reader = Tool(
        "double",
        "Double a number",
        "math.double",
        read,
        input_schema,
        {"type": "integer"},
        read_only=True,
    )
    writer = Tool(
        "record",
        "Record a number",
        "ledger.record",
        write,
        input_schema,
        {"type": "integer"},
        permissions=frozenset({"ledger:write"}),
        precondition=lambda args, access: args["value"] <= 10,
        postcondition=lambda args, output: ledger == [args["value"]],
    )
    steps = (Step("result", "math.double", {"value": 2}),)
    expected = {"result": 4}
    access = Access(frozenset({"ledger:write"}))
    category = "completion"
    expected_status, expected_failure = Status.SUCCESS, None
    if case_id == "direct":
        steps, expected = (), {"direct": 4}
    elif case_id == "dependent_reads":
        steps = (
            Step("first", "math.double", {"value": 2}),
            Step("result", "math.double", {"value": Ref("first")}),
        )
        expected = {"first": 4, "result": 8}
    elif case_id in {"denied_write", "business_limit", "lost_write_response", "false_write_ack"}:
        category = "fault"
        value = 100 if case_id == "business_limit" else 4
        steps = (Step("result", "ledger.record", {"value": value}),)
        if case_id == "denied_write":
            access = Access()
            expected_status, expected_failure = Status.BLOCKED, Failure.PERMISSION
        elif case_id == "business_limit":
            expected_status, expected_failure = Status.BLOCKED, Failure.PRECONDITION
        elif case_id == "lost_write_response":
            expected_status, expected_failure = Status.UNKNOWN, Failure.TIMEOUT
        else:
            expected_status, expected_failure = Status.UNKNOWN, Failure.POSTCONDITION
    elif case_id == "wrong_record":
        category = "fault"

        async def wrong_read(value: int) -> dict:
            return {"id": "other", "amount": 4}

        reader = replace(
            reader,
            handler=wrong_read,
            output_schema={
                "type": "object",
                "properties": {"id": {"type": "string"}, "amount": {"type": "integer"}},
                "required": ["id", "amount"],
                "additionalProperties": False,
            },
            postcondition=lambda args, output: output["id"] == "requested",
        )
        steps = (
            Step("first", "math.double", {"value": 2}),
            Step("result", "ledger.record", {"value": Ref("first", ("amount",))}),
        )
        expected_status, expected_failure = Status.FAILED, Failure.POSTCONDITION
    elif case_id not in {"single_read", "transient_read"}:
        raise ValueError(f"Unknown case: {case_id}")

    # Irrelevant tools expose that capability-constrained ranking is not a test
    # of full-catalog model selection. Their presence cannot test model confusion.
    distractions = tuple(
        replace(reader, name=f"unrelated_{i}", capability=f"unrelated.{i}") for i in range(5)
    )

    def grade(result: RunResult) -> Grade:
        if category == "completion":
            goal = dict(result.outputs) == expected
            policy_ok = not ledger
        else:
            goal = ledger == [4] if case_id == "lost_write_response" else False
            policy_ok = ledger == [4] if case_id == "lost_write_response" else not ledger
        behavior = result.status == expected_status and result.failure == expected_failure
        return Grade(goal, policy_ok, behavior and policy_ok)

    return Scenario(
        Task(case_id, lambda outputs: dict(outputs) == expected, Plan(steps, direct_result=4)),
        ToolRegistry((reader, writer, *distractions)),
        access,
        category,
        grade,
    )


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completion = [row for row in rows if row["category"] == "completion"]
    times = sorted(row["trace"]["elapsed_seconds"] for row in rows)
    return {
        "attempts": len(rows),
        "completion_attempts": len(completion),
        "completion_successes": sum(row["grade"]["goal_satisfied"] for row in completion),
        "completion_success_rate": (
            sum(row["grade"]["goal_satisfied"] for row in completion) / len(completion)
            if completion
            else None
        ),
        "expected_behavior_rate": sum(row["grade"]["expected_behavior"] for row in rows)
        / len(rows),
        "policy_violations": sum(not row["grade"]["policy_ok"] for row in rows),
        "false_successes": sum(
            row["trace"]["verified"] and not row["grade"]["goal_satisfied"] for row in rows
        ),
        "tool_calls": sum(row["trace"]["calls"] for row in rows),
        "retries": sum(row["trace"]["retries"] for row in rows),
        "median_latency_seconds": statistics.median(times),
        "p95_latency_seconds": times[max(0, math.ceil(len(times) * 0.95) - 1)],
        "statuses": dict(Counter(row["trace"]["status"] for row in rows)),
        "failures": dict(
            Counter(row["trace"]["failure"] for row in rows if row["trace"]["failure"])
        ),
        "estimated_cost": None,
    }


async def evaluate(*, repetitions: int = 3, seed: int = 0) -> dict[str, Any]:
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    budget = Budget(max_calls=8, max_retries=1, retry_delay_seconds=0.001)
    schedule = [
        (trial, case, configuration)
        for trial in range(repetitions)
        for case in CASE_IDS
        for configuration in CONFIGURATIONS
    ]
    random.Random(seed).shuffle(schedule)
    rows = []
    for trial, case, configuration in schedule:
        scenario = _scenario(case)
        engine = Orchestrator(
            scenario.registry,
            adaptive_tools=configuration.ranked_tools,
            recovery=configuration.recovery,
            fixed_strategy=Strategy.PLAN,
        )
        result = await engine.run(scenario.task, access=scenario.access, budget=budget)
        rows.append(
            {
                "case": case,
                "category": scenario.category,
                "trial": trial,
                "configuration": configuration.name,
                "grade": asdict(scenario.grade(result)),
                "trace": result.trace(),
            }
        )
    rows.sort(key=lambda row: (row["configuration"], row["case"], row["trial"]))
    # Includes implementation and fixture bytes, avoiding reliance on a mutable
    # package version for reproducing an editable development checkout.
    source_hash = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        source_hash.update(path.name.encode())
        source_hash.update(path.read_text(encoding="utf-8").encode())
    return {
        "schema_version": 1,
        "suite": "orqen-local-faults-v1",
        "evidence": "Deterministic regression fixtures; not held-out, LLM, or AgentArch results",
        "source_sha256": source_hash.hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "orqen": version("orqen"),
            "jsonschema": version("jsonschema"),
        },
        "repetitions": repetitions,
        "schedule_seed": seed,
        "budget": asdict(budget),
        "configurations": [asdict(config) for config in CONFIGURATIONS],
        "summaries": {
            config.name: _summary([row for row in rows if row["configuration"] == config.name])
            for config in CONFIGURATIONS
        },
        "rows": rows,
        "limitations": [
            "All modes enforce the same application contracts and permissions.",
            "All modes use one sequential executor; strategy labels are not a treatment.",
            "Ranking only changes ordering within an explicit capability, not model context.",
            "Fixtures are deterministic and visible during development, not held-out evidence.",
            "Repeated trials measure runtime variation, not stochastic model reliability.",
            "No model was called; tokens, selection accuracy, and monetary cost are unmeasured.",
            "Latency includes checks and retry delay; no statistical performance claim is made.",
        ],
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    """Replace a report atomically, retaining the previous checkpoint on failure."""
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_traces(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in report["rows"]:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
