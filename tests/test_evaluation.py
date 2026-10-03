import asyncio
import json
import subprocess
import sys
from dataclasses import replace

import pytest

from orqen.evaluation import CASE_IDS, CONFIGURATIONS, evaluate, write_report, write_traces


def test_factorial_experiment_is_fair_and_reports_expected_limits(tmp_path):
    report = asyncio.run(evaluate(repetitions=2, seed=7))
    assert len(report["rows"]) == 2 * len(CASE_IDS) * len(CONFIGURATIONS)
    for name, summary in report["summaries"].items():
        assert summary["attempts"] == 18
        assert summary["completion_attempts"] == 8
        assert summary["policy_violations"] == summary["false_successes"] == 0
        assert summary["estimated_cost"] is None
        has_recovery = "recovery" in name
        assert summary["completion_successes"] == (8 if has_recovery else 6)
        assert summary["retries"] == (2 if has_recovery else 0)
    # Ranking must not be credited with recovery's effect.
    for a, b in [("fixed", "ranking_only"), ("recovery_only", "ranking_and_recovery")]:
        assert (
            report["summaries"][a]["completion_success_rate"]
            == (report["summaries"][b]["completion_success_rate"])
        )
    assert "not held-out" in report["evidence"]
    path, traces = tmp_path / "report.json", tmp_path / "traces.jsonl"
    write_report(report, path)
    write_traces(report, traces)
    assert json.loads(path.read_text())["source_sha256"] == report["source_sha256"]
    assert len(traces.read_text().splitlines()) == 72
    assert "Injected lost acknowledgement" not in traces.read_text()


def test_unknown_write_outcome_is_not_counted_as_failed_state_change():
    report = asyncio.run(evaluate(repetitions=1))
    rows = [row for row in report["rows"] if row["case"] == "lost_write_response"]
    assert all(row["grade"]["goal_satisfied"] for row in rows)
    assert all(row["grade"]["expected_behavior"] for row in rows)
    assert all(row["trace"]["status"] == "unknown" for row in rows)
    assert all(row["trace"]["calls"] == 1 for row in rows)


@pytest.mark.parametrize("count", [0, -1, True])
def test_invalid_repetition_counts_rejected(count):
    with pytest.raises(ValueError):
        asyncio.run(evaluate(repetitions=count))


def test_cli_writes_a_report(tmp_path):
    report_path = tmp_path / "out.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "orqen.cli",
            "evaluate",
            "--repetitions",
            "1",
            "--output",
            str(report_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert len(json.loads(report_path.read_text())["rows"]) == 36


def test_cli_rejects_overlapping_output_paths(tmp_path):
    path = str(tmp_path / "out.json")
    completed = subprocess.run(
        [sys.executable, "-m", "orqen.cli", "evaluate", "--output", path, "--traces", path],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2


def test_independent_grader_detects_falsely_claimed_success(monkeypatch):
    from orqen import Orchestrator, Status

    original = Orchestrator.run

    async def falsely_successful(self, task, **kwargs):
        result = await original(self, task, **kwargs)
        return replace(
            result, outputs={"incorrect": True}, status=Status.SUCCESS, verified=True, failure=None
        )

    monkeypatch.setattr(Orchestrator, "run", falsely_successful)
    report = asyncio.run(evaluate(repetitions=1))
    for summary in report["summaries"].values():
        assert summary["completion_successes"] == 0
        assert summary["false_successes"] > 0
