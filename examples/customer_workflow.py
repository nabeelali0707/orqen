"""A local, deterministic example; no model credentials or external systems needed."""

import asyncio
import json

from orqen import Orchestrator, Plan, Ref, Step, Task, Tool, ToolRegistry


async def lookup_customer(customer_id: str) -> dict:
    return {"id": customer_id, "tier": "premium"}


async def select_queue(tier: str) -> dict:
    return {"queue": "priority" if tier == "premium" else "standard"}


def string_input(name: str) -> dict:
    return {
        "type": "object",
        "properties": {name: {"type": "string"}},
        "required": [name],
        "additionalProperties": False,
    }


async def main() -> None:
    registry = ToolRegistry(
        (
            Tool(
                "customer_lookup",
                "Retrieve customer tier",
                "customer.lookup",
                lookup_customer,
                string_input("customer_id"),
                {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "tier": {"enum": ["premium", "standard"]},
                    },
                    "required": ["id", "tier"],
                    "additionalProperties": False,
                },
                read_only=True,
            ),
            Tool(
                "queue_selector",
                "Determine support queue",
                "support.queue",
                select_queue,
                string_input("tier"),
                {
                    "type": "object",
                    "properties": {"queue": {"type": "string"}},
                    "required": ["queue"],
                    "additionalProperties": False,
                },
                read_only=True,
            ),
        )
    )
    task = Task(
        "Find the support queue for customer c-123",
        verify=lambda outputs: outputs["route"]["queue"] == "priority",
        plan=Plan(
            (
                Step("customer", "customer.lookup", {"customer_id": "c-123"}),
                Step("route", "support.queue", {"tier": Ref("customer", ("tier",))}),
            )
        ),
    )
    result = await Orchestrator(registry).run(task)
    print(json.dumps({"outputs": result.outputs, "trace": result.trace()}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
