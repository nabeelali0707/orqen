"""Transparent baseline policies, replaceable without changing execution safeguards."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Protocol

from .models import Analysis, Plan, Ref, Step, Strategy, Task, Tool
from .registry import ToolRegistry


def references(value: Any) -> set[str]:
    if isinstance(value, Ref):
        return {value.step}
    if isinstance(value, Mapping):
        return set().union(*(references(v) for v in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(references(v) for v in value))
    return set()


def ordered_steps(plan: Plan, max_steps: int) -> tuple[Step, ...]:
    """Validate the entire dependency graph before any side effects occur."""
    if len(plan.steps) > max_steps:
        raise ValueError("Step budget exceeded")
    ids = [step.id for step in plan.steps]
    if any(not name.strip() for name in ids) or len(set(ids)) != len(ids):
        raise ValueError("Step identifiers must be nonempty and unique")
    if "direct" in ids:
        raise ValueError("The identifier 'direct' is reserved")
    dependencies = {}
    for step in plan.steps:
        if not step.capability.strip() or not isinstance(step.arguments, Mapping):
            raise ValueError("Each step needs a capability and argument mapping")
        deps = set(step.depends_on) | references(step.arguments)
        if not deps <= set(ids):
            raise ValueError("Unknown dependency")
        dependencies[step.id] = deps
    pending = list(plan.steps)
    result: list[Step] = []
    done: set[str] = set()
    while pending:
        ready = [step for step in pending if dependencies[step.id] <= done]
        if not ready:
            raise ValueError("Cyclic dependencies")
        for step in ready:
            result.append(step)
            done.add(step.id)
            pending.remove(step)
    return tuple(result)


class TaskAnalyzer:
    def analyze(self, task: Task, plan: Plan) -> Analysis:
        dependencies = sum(
            len(set(step.depends_on) | references(step.arguments)) for step in plan.steps
        )
        count = len(plan.steps)
        return Analysis(
            task_type="direct" if not count else "workflow" if count > 1 else "tool_call",
            complexity="low" if count < 2 else "high" if count > 5 else "medium",
            dependencies=dependencies,
            risk=task.risk,
            step_count=count,
        )


class StrategyRouter:
    def select(self, analysis: Analysis) -> tuple[Strategy, str]:
        if not analysis.step_count:
            return Strategy.DIRECT, "No tool steps are required"
        if analysis.step_count == 1:
            return Strategy.FUNCTION, "One bounded tool step is required"
        return Strategy.PLAN, "Multiple steps require explicit execution ordering"


class ToolRouter:
    def __init__(self, registry: ToolRegistry, adaptive: bool = True) -> None:
        self.registry = registry
        self.adaptive = adaptive

    def candidates(self, step: Step) -> tuple[Tool, ...]:
        # Capability is an application-defined semantic contract. Never cross it
        # merely because a tool description has overlapping words.
        tools = [tool for tool in self.registry.all() if tool.capability == step.capability]
        if step.tool:
            return tuple(tool for tool in tools if tool.name == step.tool)
        if not self.adaptive:
            return tuple(tools)
        terms = set(re.findall(r"\w+", step.query.lower()))

        def score(tool: Tool) -> int:
            words = set(re.findall(r"\w+", f"{tool.name} {tool.description}".lower()))
            return len(terms & words)

        return tuple(sorted(tools, key=lambda tool: (-score(tool), tool.name)))


class Planner(Protocol):
    """Provider adapter returns a proposal; execution retains access control.

    Catalog contains metadata and schemas only, never handlers or credentials.
    An adapter must not execute side effects while planning.
    """

    async def plan(self, goal: str, catalog: tuple[dict[str, Any], ...]) -> Plan: ...
