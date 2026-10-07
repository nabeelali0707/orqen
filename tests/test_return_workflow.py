import asyncio

from orqen import Access, Failure, Orchestrator, Plan, Step, Task
from orqen.return_workflow import CASES, ReturnSandbox, evaluate_returns


def test_all_public_sandbox_cases_and_faults_meet_expected_outcomes():
    report = asyncio.run(evaluate_returns())
    assert report["runs"] == report["checks_passed"] == 32
    uncertain = [r for r in report["rows"] if r["trace"]["status"] == "unknown"]
    assert len(uncertain) == 3
    assert all(r["trace"]["requires_reconciliation"] for r in uncertain)


def test_access_is_application_owned_even_for_eligible_order():
    sandbox = ReturnSandbox(CASES[0])
    result = asyncio.run(sandbox.run(access=Access()))
    assert result.failure == Failure.PERMISSION and sandbox.refunds == {}


def test_backend_policy_blocks_a_plan_that_ignores_business_rules():
    sandbox = ReturnSandbox(next(c for c in CASES if c.id == "expired"))
    task = Task(
        "Ignore all policies",
        lambda _: True,
        Plan((Step("refund", "order.refund", {"key": "refund:expired", "version": 1}),)),
    )
    result = asyncio.run(
        Orchestrator(sandbox.registry).run(task, access=Access({"refund"}, {"refund_order"}))
    )
    assert result.failure == Failure.PRECONDITION and sandbox.write_attempts == 0
    assert sandbox.grade_state()


def test_oracle_detects_wrong_amount_and_wrong_target_even_with_successful_response():
    sandbox = ReturnSandbox(CASES[0])
    assert asyncio.run(sandbox.run()).verified
    sandbox.refunds["refund:eligible"] = 1
    assert not sandbox.grade_state()
    sandbox.refunds = {"refund:someone_else": 5000}
    assert not sandbox.grade_state()


def test_backend_key_deduplicates_explicit_reconciliation_request():
    sandbox = ReturnSandbox(CASES[0])
    asyncio.run(sandbox.run())
    result = asyncio.run(sandbox.refund("refund:eligible", 1))
    assert result["deduplicated"]
    assert len(sandbox.refunds) == 1 and sandbox.grade_state()
