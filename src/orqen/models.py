"""Application-owned contracts; planners can propose actions but cannot grant access."""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Strategy(StrEnum):
    DIRECT = "direct"
    FUNCTION = "function_calling"
    PLAN = "plan_and_execute"
    MULTI_AGENT = "multi_agent"


class Status(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class Failure(StrEnum):
    PLAN = "invalid_plan"
    PLANNER = "planner_transport_error"
    UNSUPPORTED = "unsupported_strategy"
    NO_TOOL = "no_matching_tool"
    UNAVAILABLE = "tool_unavailable"
    PERMISSION = "permission_denied"
    CONFIRMATION = "confirmation_required"
    PRECONDITION = "precondition_failed"
    POSTCONDITION = "postcondition_failed"
    ARGUMENTS = "invalid_arguments"
    OUTPUT = "invalid_output"
    VERIFICATION = "verification_failed"
    TRANSIENT = "transient_error"
    TIMEOUT = "timeout"
    TOOL = "tool_error"
    BUDGET = "budget_exhausted"


class TransientToolError(Exception):
    """Adapter explicitly identifies a transient failure. Only reads are retried."""


@dataclass(frozen=True)
class Ref:
    """Reference a previous step's output using dictionary keys or array indices."""

    step: str
    path: tuple[str | int, ...] = ()


@dataclass(frozen=True)
class Step:
    id: str
    capability: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    query: str = ""
    tool: str | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class Plan:
    steps: tuple[Step, ...] = ()
    direct_result: Any = None
    strategy: Strategy | None = None


@dataclass(frozen=True)
class Task:
    goal: str
    verify: Callable[[Mapping[str, Any]], bool | Awaitable[bool]]
    plan: Plan | None = None
    # These are application hints, not authorization decisions.
    risk: str = "low"


@dataclass(frozen=True)
class Access:
    permissions: frozenset[str] = frozenset()
    confirmed_tools: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "permissions", frozenset(self.permissions))
        object.__setattr__(self, "confirmed_tools", frozenset(self.confirmed_tools))


@dataclass(frozen=True)
class Budget:
    max_calls: int = 12
    max_steps: int = 20
    max_retries: int = 1
    timeout_seconds: float = 30.0
    retry_delay_seconds: float = 0.01
    max_planner_calls: int = 2

    def __post_init__(self) -> None:
        for name in ("max_calls", "max_steps", "max_retries", "max_planner_calls"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        for name in ("timeout_seconds", "retry_delay_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.timeout_seconds == 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    capability: str
    handler: Callable[..., Awaitable[Any]]
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    permissions: frozenset[str] = frozenset()
    # Opt in explicitly to read retries; an omitted declaration is conservative.
    read_only: bool = False
    requires_confirmation: bool = False
    available: bool = True
    timeout_seconds: float = 10.0
    precondition: Callable[[Mapping[str, Any], Access], bool | Awaitable[bool]] | None = None
    postcondition: Callable[[Mapping[str, Any], Any], bool | Awaitable[bool]] | None = None


@dataclass(frozen=True)
class Analysis:
    task_type: str
    complexity: str
    dependencies: int
    risk: str
    step_count: int


@dataclass(frozen=True)
class Event:
    kind: str
    step: str | None = None
    tool: str | None = None
    failure: Failure | None = None
    attempt: int | None = None
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: Status
    strategy: Strategy | None
    reason: str
    outputs: Mapping[str, Any]
    failure: Failure | None
    events: tuple[Event, ...]
    calls: int
    retries: int
    elapsed_seconds: float
    verified: bool
    analysis: Analysis | None = None
    estimated_cost: float | None = None
    planner_calls: int = 0
    write_steps: tuple[str, ...] = ()

    @property
    def requires_reconciliation(self) -> bool:
        """A non-successful run attempted writes; do not infer safe whole-run replay."""
        return bool(self.write_steps) and self.status != Status.SUCCESS

    def trace(self) -> dict[str, Any]:
        """Metadata only: no task text, arguments, results, or exception messages."""
        from dataclasses import asdict

        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "strategy": self.strategy.value if self.strategy else None,
            "reason": self.reason,
            "failure": self.failure.value if self.failure else None,
            "events": [asdict(event) for event in self.events],
            "calls": self.calls,
            "planner_calls": self.planner_calls,
            "write_steps": list(self.write_steps),
            "requires_reconciliation": self.requires_reconciliation,
            "retries": self.retries,
            "elapsed_seconds": self.elapsed_seconds,
            "verified": self.verified,
            "estimated_cost": self.estimated_cost,
        }
