"""Exercise the JSON planning boundary using an offline response, not an LLM."""

import asyncio
import json

from orqen import JSONPlanner, Orchestrator, PlanningRequest, Task, Tool, ToolRegistry


async def add(a: int, b: int) -> int:
    return a + b


async def replay_response(request: PlanningRequest) -> str:
    # A real integration supplies an async callback that sends the goal, catalog,
    # and response schema to a model, then returns only its generated JSON text.
    # This canned response tests the integration boundary without spending tokens.
    return json.dumps(
        {
            "kind": "tools",
            "steps": [
                {
                    "id": "sum",
                    "tool": "add",
                    "depends_on": [],
                    "arguments": {"a": {"literal": 2}, "b": {"literal": 3}},
                }
            ],
        }
    )


async def main() -> None:
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
    engine = Orchestrator(ToolRegistry((tool,)), planner=JSONPlanner(replay_response))
    result = await engine.run(Task("Add 2 and 3", lambda outputs: outputs["sum"] == 5))
    print(
        json.dumps(
            {
                "evidence": "Offline response replay; no LLM invoked",
                "outputs": result.outputs,
                "trace": result.trace(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
