"""Sequential async execution with validation, verification, and conservative recovery."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from copy import deepcopy
from time import perf_counter
from typing import Any
from uuid import uuid4

from .models import (
    Access,
    Budget,
    Event,
    Failure,
    Plan,
    Ref,
    RunResult,
    Status,
    Strategy,
    Task,
    TransientToolError,
)
from .multi_agent import ReviewPlanner
from .planning import CatalogExpansionRequested, PlanningTransportError
from .registry import ResultValidator, ToolRegistry
from .retrieval import CatalogPolicy
from .routing import Planner, StrategyRouter, TaskAnalyzer, ToolRouter, ordered_steps, references


def _resolve(value: Any, outputs: Mapping[str, Any]) -> Any:
    if isinstance(value, Ref):
        result = outputs[value.step]
        for part in value.path:
            if isinstance(result, list):
                if type(part) is not int or part < 0:
                    raise ValueError("Array reference needs a nonnegative integer")
            elif isinstance(result, dict):
                if type(part) is not str:
                    raise ValueError("Object reference needs a string key")
            else:
                raise ValueError("Reference traverses a scalar")
            result = result[part]
        return deepcopy(result)
    if isinstance(value, Mapping):
        return {key: _resolve(child, outputs) for key, child in value.items()}
    if isinstance(value, list):
        return [_resolve(child, outputs) for child in value]
    return deepcopy(value)


async def _check(callback: Any, deadline: float, *arguments: Any) -> bool:
    """Trusted checks may read state; require literal True and honor run deadlines."""
    if perf_counter() >= deadline:
        raise TimeoutError
    async with asyncio.timeout(max(0, deadline - perf_counter())):
        value = callback(*deepcopy(arguments))
        if inspect.isawaitable(value):
            value = await value
    if perf_counter() >= deadline:
        raise TimeoutError
    return value is True


class Orchestrator:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        planner: Planner | None = None,
        adaptive_tools: bool = False,
        fixed_strategy: Strategy | None = None,
        recovery: bool = True,
        catalog_policy: CatalogPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.planner = planner
        self.tool_router = ToolRouter(registry, adaptive_tools)
        self.strategy_router = StrategyRouter()
        self.analyzer = TaskAnalyzer()
        self.fixed_strategy = fixed_strategy
        self.recovery = recovery
        self.catalog_policy = catalog_policy or CatalogPolicy()

    async def run(
        self,
        task: Task,
        *,
        access: Access | None = None,
        budget: Budget | None = None,
    ) -> RunResult:
        access, budget = access or Access(), budget or Budget()
        start = perf_counter()
        deadline = start + budget.timeout_seconds
        run_id = str(uuid4())
        events: list[Event] = []
        outputs: dict[str, Any] = {}
        write_steps: list[str] = []
        calls = retries = planner_calls = 0
        strategy = None
        analysis = None
        reason = "Execution has not started"

        def finish(status: Status, failure: Failure | None = None) -> RunResult:
            events.append(Event("finished", failure=failure))
            return RunResult(
                run_id,
                status,
                strategy,
                reason,
                deepcopy(outputs),
                failure,
                tuple(events),
                calls,
                retries,
                perf_counter() - start,
                status == Status.SUCCESS,
                analysis,
                planner_calls=planner_calls,
                write_steps=tuple(write_steps),
            )

        if not callable(task.verify):
            return finish(Status.BLOCKED, Failure.VERIFICATION)
        try:
            plan = task.plan
            if plan is None:
                if self.planner is None:
                    return finish(Status.BLOCKED, Failure.PLAN)
                catalog = tuple(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "capability": tool.capability,
                        "input_schema": tool.input_schema,
                        "output_schema": tool.output_schema,
                        "read_only": tool.read_only,
                        "requires_confirmation": tool.requires_confirmation,
                    }
                    for tool in self.registry.all()
                    if tool.available and tool.permissions <= access.permissions
                )
                selected = self.catalog_policy.select(task.goal, catalog)
                call_cost = 2 if isinstance(self.planner, ReviewPlanner) else 1
                while True:
                    if (
                        planner_calls + call_cost > budget.max_planner_calls
                        or perf_counter() >= deadline
                    ):
                        return finish(Status.BLOCKED, Failure.BUDGET)

                    def count_call() -> None:
                        nonlocal planner_calls
                        planner_calls += 1

                    events.append(
                        Event(
                            "catalog_offered",
                            candidates=tuple(tool["name"] for tool in selected),
                            attempt=planner_calls + 1,
                        )
                    )
                    try:
                        async with asyncio.timeout(max(0, deadline - perf_counter())):
                            if isinstance(self.planner, ReviewPlanner):
                                plan = await self.planner.plan_counted(
                                    task.goal, deepcopy(selected), count_call
                                )
                            else:
                                count_call()
                                plan = await self.planner.plan(task.goal, deepcopy(selected))
                        break
                    except CatalogExpansionRequested:
                        if len(selected) == len(catalog):
                            return finish(Status.BLOCKED, Failure.NO_TOOL)
                        selected = catalog
                        events.append(Event("catalog_expanded"))
            if not isinstance(plan, Plan):
                return finish(Status.BLOCKED, Failure.PLAN)
            plan = deepcopy(plan)
            if len(plan.steps) > budget.max_steps:
                return finish(Status.BLOCKED, Failure.BUDGET)
            steps = ordered_steps(plan, budget.max_steps)
            analysis = self.analyzer.analyze(task, plan)
            strategy, reason = self.strategy_router.select(analysis)
            override = self.fixed_strategy or plan.strategy
            if override is not None:
                strategy = Strategy(override)
                reason = "Explicit strategy configuration"
            if strategy == Strategy.MULTI_AGENT and not (
                task.plan is None and isinstance(self.planner, ReviewPlanner)
            ):
                return finish(Status.BLOCKED, Failure.UNSUPPORTED)
            if (strategy == Strategy.DIRECT and steps) or (
                strategy == Strategy.FUNCTION and len(steps) > 1
            ):
                return finish(Status.BLOCKED, Failure.UNSUPPORTED)
        except TimeoutError:
            return finish(Status.BLOCKED, Failure.BUDGET)
        except PlanningTransportError:
            return finish(Status.BLOCKED, Failure.PLANNER)
        except Exception:
            return finish(Status.BLOCKED, Failure.PLAN)

        events.append(Event("analyzed"))
        if not steps:
            if not ResultValidator.matches({}, plan.direct_result):
                return finish(Status.FAILED, Failure.OUTPUT)
            outputs["direct"] = deepcopy(plan.direct_result)

        # Validate what is knowable before any handler runs. Dynamic preconditions
        # and reference-dependent arguments are checked again at invocation time.
        if len(steps) > budget.max_calls:
            return finish(Status.BLOCKED, Failure.BUDGET)
        prepared = {}
        for step in steps:
            if perf_counter() >= deadline or calls >= budget.max_calls:
                return finish(Status.BLOCKED, Failure.BUDGET)
            candidates = self.tool_router.candidates(step)
            events.append(Event("routed", step.id, candidates=tuple(t.name for t in candidates)))
            if not candidates:
                return finish(Status.BLOCKED, Failure.NO_TOOL)
            # Alternative tools are considered only for declared unavailability.
            # Permission/argument errors never cause silent fallback.
            tool = candidates[0]
            if not tool.available:
                events.append(Event("unavailable", step.id, tool.name, Failure.UNAVAILABLE))
                available = [candidate for candidate in candidates[1:] if candidate.available]
                if not self.recovery or step.tool or not available:
                    return finish(Status.BLOCKED, Failure.UNAVAILABLE)
                tool = available[0]
                events.append(Event("fallback", step.id, tool.name))
            if not tool.permissions <= access.permissions:
                events.append(Event("rejected", step.id, tool.name, Failure.PERMISSION))
                return finish(Status.BLOCKED, Failure.PERMISSION)
            if tool.requires_confirmation and tool.name not in access.confirmed_tools:
                return finish(Status.BLOCKED, Failure.CONFIRMATION)
            if not references(step.arguments):
                try:
                    literal_arguments = _resolve(step.arguments, {})
                except Exception:
                    return finish(Status.BLOCKED, Failure.ARGUMENTS)
                if not ResultValidator.matches(tool.input_schema, literal_arguments):
                    return finish(Status.BLOCKED, Failure.ARGUMENTS)
            prepared[step.id] = tool

        events.append(Event("preflight_passed"))
        for step in steps:
            if perf_counter() >= deadline or calls >= budget.max_calls:
                return finish(Status.BLOCKED, Failure.BUDGET)
            tool = prepared[step.id]
            try:
                arguments = _resolve(step.arguments, outputs)
            except Exception:
                return finish(Status.BLOCKED, Failure.ARGUMENTS)
            if not ResultValidator.matches(tool.input_schema, arguments):
                return finish(Status.BLOCKED, Failure.ARGUMENTS)

            attempt = 0
            while True:
                remaining = deadline - perf_counter()
                if remaining <= 0 or calls >= budget.max_calls:
                    return finish(Status.BLOCKED, Failure.BUDGET)
                if tool.precondition is not None:
                    try:
                        allowed = await _check(tool.precondition, deadline, arguments, access)
                    except TimeoutError:
                        return finish(Status.BLOCKED, Failure.BUDGET)
                    except Exception:
                        allowed = False
                    events.append(
                        Event(
                            "precondition_checked",
                            step.id,
                            tool.name,
                            None if allowed else Failure.PRECONDITION,
                        )
                    )
                    if not allowed:
                        return finish(Status.BLOCKED, Failure.PRECONDITION)
                if attempt:
                    retries += 1
                attempt += 1
                calls += 1
                if not tool.read_only:
                    write_steps.append(step.id)
                events.append(Event("called", step.id, tool.name, attempt=attempt))
                error = None
                call_deadline = min(deadline, perf_counter() + tool.timeout_seconds)
                try:
                    async with asyncio.timeout(max(0, call_deadline - perf_counter())):
                        output = await tool.handler(**deepcopy(arguments))
                    # A noncooperative handler may suppress cancellation or block
                    # the event loop. Never claim timely success in that case.
                    if perf_counter() >= call_deadline:
                        error = Failure.TIMEOUT
                except TimeoutError:
                    error = Failure.TIMEOUT
                except TransientToolError:
                    error = Failure.TRANSIENT
                except Exception:
                    error = Failure.TOOL
                if error is None:
                    break
                events.append(Event("call_failed", step.id, tool.name, error, attempt))
                if not tool.read_only:
                    # A write may have happened even when its adapter raised.
                    return finish(Status.UNKNOWN, error)
                if (
                    not self.recovery
                    or error not in {Failure.TRANSIENT, Failure.TIMEOUT}
                    or attempt > budget.max_retries
                ):
                    return finish(Status.FAILED, error)
                delay = budget.retry_delay_seconds * 2 ** (attempt - 1)
                if calls >= budget.max_calls or perf_counter() + delay >= deadline:
                    return finish(Status.BLOCKED, Failure.BUDGET)
                events.append(Event("retry_scheduled", step.id, tool.name, error, attempt))
                await asyncio.sleep(delay)

            if not ResultValidator.matches(tool.output_schema, output):
                return finish(Status.FAILED if tool.read_only else Status.UNKNOWN, Failure.OUTPUT)
            if tool.postcondition is not None:
                try:
                    verified = await _check(tool.postcondition, deadline, arguments, output)
                except TimeoutError:
                    return finish(
                        Status.BLOCKED if tool.read_only else Status.UNKNOWN, Failure.BUDGET
                    )
                except Exception:
                    verified = False
                events.append(
                    Event(
                        "postcondition_checked",
                        step.id,
                        tool.name,
                        None if verified else Failure.POSTCONDITION,
                    )
                )
                if not verified:
                    return finish(
                        Status.FAILED if tool.read_only else Status.UNKNOWN, Failure.POSTCONDITION
                    )
            outputs[step.id] = deepcopy(output)
            events.append(Event("output_validated", step.id, tool.name))

        if perf_counter() >= deadline:
            return finish(Status.UNKNOWN if write_steps else Status.BLOCKED, Failure.BUDGET)
        try:
            verified = await _check(task.verify, deadline, outputs)
        except TimeoutError:
            return finish(Status.UNKNOWN if write_steps else Status.BLOCKED, Failure.BUDGET)
        except Exception:
            return finish(Status.UNKNOWN if write_steps else Status.FAILED, Failure.VERIFICATION)
        if perf_counter() >= deadline:
            return finish(Status.UNKNOWN if write_steps else Status.BLOCKED, Failure.BUDGET)
        events.append(Event("verified" if verified else "verification_failed"))
        return finish(
            Status.SUCCESS if verified else Status.FAILED,
            None if verified else Failure.VERIFICATION,
        )
