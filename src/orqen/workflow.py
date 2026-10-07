"""Bounded observation-driven workflows with application-owned decisions and grading."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any

from .engine import Orchestrator, _check
from .models import Access, Budget, Failure, RunResult, Status, Task

Observations = tuple[Mapping[str, Any], ...]
NextTask = Callable[[Observations], Task | None | Awaitable[Task | None]]


@dataclass(frozen=True)
class WorkflowResult:
    status: Status
    failure: Failure | None
    stages: tuple[RunResult, ...]
    elapsed_seconds: float

    @property
    def verified(self) -> bool:
        return self.status == Status.SUCCESS

    @property
    def requires_reconciliation(self) -> bool:
        return not self.verified and any(stage.write_steps for stage in self.stages)

    def trace(self) -> dict[str, Any]:
        """Metadata only; stage observations are available in memory, never exported."""
        return {
            "status": self.status.value,
            "failure": self.failure.value if self.failure else None,
            "verified": self.verified,
            "requires_reconciliation": self.requires_reconciliation,
            "calls": sum(s.calls for s in self.stages),
            "planner_calls": sum(s.planner_calls for s in self.stages),
            "elapsed_seconds": self.elapsed_seconds,
            "stages": [stage.trace() for stage in self.stages],
        }


class WorkflowRunner:
    """Select tasks from verified observations under one execution budget.

    next_task and verify are trusted application code, never model-supplied code.
    None ends selection and triggers independent final verification. A failed or
    uncertain stage always stops; the runner never restarts or replays a stage.
    This is in-process control flow, not durable execution or a sandbox.
    """

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator

    async def run(
        self,
        next_task: NextTask,
        verify: Callable[[Observations], bool | Awaitable[bool]],
        *,
        access: Access | None = None,
        budget: Budget | None = None,
        max_stages: int = 8,
    ) -> WorkflowResult:
        if type(max_stages) is not int or not 1 <= max_stages <= 1000:
            raise ValueError("max_stages must be between 1 and 1000")
        if not callable(next_task) or not callable(verify):
            raise TypeError("Application selection and verification callbacks are required")
        access, budget = access or Access(), budget or Budget()
        start = perf_counter()
        deadline = start + budget.timeout_seconds
        stages: list[RunResult] = []
        used_steps = 0

        def finish(status: Status, failure: Failure | None = None) -> WorkflowResult:
            return WorkflowResult(status, failure, tuple(stages), perf_counter() - start)

        def interrupted(failure: Failure) -> WorkflowResult:
            status = Status.UNKNOWN if any(s.write_steps for s in stages) else Status.BLOCKED
            return finish(status, failure)

        while True:
            if perf_counter() >= deadline:
                return interrupted(Failure.BUDGET)
            observations = tuple(deepcopy(stage.outputs) for stage in stages)
            try:
                async with asyncio.timeout(max(0, deadline - perf_counter())):
                    task = next_task(deepcopy(observations))
                    if inspect.isawaitable(task):
                        task = await task
                if perf_counter() >= deadline:
                    return interrupted(Failure.BUDGET)
            except TimeoutError:
                return interrupted(Failure.BUDGET)
            except Exception:
                return interrupted(Failure.PLAN)

            if task is None:
                try:
                    verified = await _check(verify, deadline, observations)
                except TimeoutError:
                    return interrupted(Failure.BUDGET)
                except Exception:
                    return interrupted(Failure.VERIFICATION)
                return finish(
                    Status.SUCCESS if verified else Status.FAILED,
                    None if verified else Failure.VERIFICATION,
                )
            if not isinstance(task, Task):
                return interrupted(Failure.PLAN)
            if len(stages) >= max_stages:
                return interrupted(Failure.BUDGET)
            remaining = deadline - perf_counter()
            if remaining <= 0:
                return interrupted(Failure.BUDGET)
            stage_budget = replace(
                budget,
                max_calls=budget.max_calls - sum(s.calls for s in stages),
                max_steps=budget.max_steps - used_steps,
                max_planner_calls=budget.max_planner_calls - sum(s.planner_calls for s in stages),
                timeout_seconds=remaining,
            )
            result = await self.orchestrator.run(task, access=access, budget=stage_budget)
            stages.append(result)
            if result.analysis is not None:
                used_steps += result.analysis.step_count
            if not result.verified:
                return finish(result.status, result.failure)
