"""A single bounded model compatibility demo, not a performance benchmark."""

from __future__ import annotations

from typing import Any

from .engine import Orchestrator
from .models import Budget, Task, Tool
from .planning import JSONPlanner
from .providers.ollama import OllamaConfig, OllamaTransport
from .registry import ToolRegistry

GOAL = "Use the add tool once to add 2 and 3. Name the tool step sum."


async def run_ollama_demo(config: OllamaConfig, *, http_transport: Any = None) -> dict[str, Any]:
    return await _run_addition_demo(
        OllamaTransport(config, http_transport=http_transport),
        config.timeout_seconds,
        "ollama-addition-smoke-v1",
    )


async def run_hosted_demo(config, *, api_key=None, allow_live=False, http_transport=None) -> dict:
    from .providers.hosted import HostedTransport

    return await _run_addition_demo(
        HostedTransport(
            config, api_key=api_key, allow_live=allow_live, http_transport=http_transport
        ),
        config.timeout_seconds,
        f"{config.provider}-addition-smoke-v1",
    )


async def _run_addition_demo(transport: Any, budget_seconds: float, suite: str) -> dict[str, Any]:
    async def add(a: int, b: int) -> int:
        return a + b

    tool = Tool(
        "add",
        "Add two integers",
        "math.add",
        add,
        {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        {"type": "integer"},
        read_only=True,
    )
    engine = Orchestrator(ToolRegistry((tool,)), planner=JSONPlanner(transport, max_steps=1))
    result = await engine.run(
        Task(GOAL, lambda outputs: outputs == {"sum": 5}),
        budget=Budget(
            max_calls=1,
            max_steps=1,
            max_retries=0,
            max_planner_calls=1,
            timeout_seconds=budget_seconds + 1,
        ),
    )
    return {
        "schema_version": 1,
        "suite": suite,
        "evidence": "Single tool-contract smoke test; not research or benchmark evidence",
        "passed": result.verified and result.calls == 1,
        "trace": result.trace(),
        "provider": transport.metadata(),
    }
