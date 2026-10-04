import asyncio

from orqen.engine import Orchestrator
from orqen.models import Budget, Failure, Plan, Strategy, Task
from orqen.multi_agent import ReviewPlanner
from orqen.registry import ToolRegistry


class Stub:
    def __init__(self, result):
        self.result = result
        self.goals = []

    async def plan(self, goal, catalog):
        self.goals.append(goal)
        return self.result


def test_reviewer_corrects_draft_and_both_calls_are_measured():
    proposer, reviewer = Stub(Plan(direct_result=4)), Stub(Plan(direct_result=5))
    engine = Orchestrator(ToolRegistry(), planner=ReviewPlanner(proposer, reviewer))
    result = asyncio.run(engine.run(Task("2+3", lambda out: out == {"direct": 5})))
    assert result.verified and result.planner_calls == 2
    assert result.strategy == Strategy.MULTI_AGENT
    assert '"direct_result": 4' in reviewer.goals[0]


def test_insufficient_budget_prevents_both_agents_from_starting():
    proposer, reviewer = Stub(Plan()), Stub(Plan())
    result = asyncio.run(
        Orchestrator(ToolRegistry(), planner=ReviewPlanner(proposer, reviewer)).run(
            Task("test", lambda _: True), budget=Budget(max_planner_calls=1)
        )
    )
    assert result.failure == Failure.BUDGET and result.planner_calls == 0
    assert not proposer.goals and not reviewer.goals


def test_strategy_label_alone_does_not_enable_multi_agent():
    result = asyncio.run(
        Orchestrator(ToolRegistry()).run(
            Task("test", lambda _: True, Plan(strategy=Strategy.MULTI_AGENT))
        )
    )
    assert result.failure == Failure.UNSUPPORTED
