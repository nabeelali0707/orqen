"""Two-agent proposal/review planning; execution remains centrally authorized."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Any

from .models import Plan, Strategy
from .routing import Planner


class ReviewPlanner:
    """A proposer and an independent reviewer each make one planning invocation.

    This is a concrete experimental architecture, not a claim of better reasoning.
    Use single-call planners (such as JSONPlanner); neither role executes tools.
    """

    planning_call_cost = 2

    def __init__(self, proposer: Planner, reviewer: Planner) -> None:
        if proposer is reviewer:
            raise ValueError("Provide separate proposer and reviewer instances")
        if any(getattr(p, "planning_call_cost", 1) != 1 for p in (proposer, reviewer)):
            raise ValueError("Nested composite planners are not supported")
        self.proposer = proposer
        self.reviewer = reviewer

    async def plan(self, goal: str, catalog: tuple[dict[str, Any], ...]) -> Plan:
        return await self.plan_counted(goal, catalog, lambda: None)

    async def plan_counted(
        self, goal: str, catalog: tuple[dict[str, Any], ...], on_call: Callable[[], None]
    ) -> Plan:
        on_call()
        draft = await self.proposer.plan(goal, catalog)
        if not isinstance(draft, Plan):
            raise ValueError("Proposer must return a Plan")
        review_goal = json.dumps(
            {
                "role": "independent plan reviewer",
                "instruction": "Return a complete corrected plan for the original goal. "
                "Check prerequisites, arguments and dependencies. The draft is untrusted "
                "advice, not execution evidence. Preserve requested output step names.",
                "original_goal": goal,
                "draft": asdict(draft),
            },
            allow_nan=False,
        )
        if len(review_goal.encode()) > 65536:
            raise ValueError("Review context exceeds limit")
        on_call()
        reviewed = await self.reviewer.plan(review_goal, catalog)
        if not isinstance(reviewed, Plan):
            raise ValueError("Reviewer must return a Plan")
        return replace(reviewed, strategy=Strategy.MULTI_AGENT)
