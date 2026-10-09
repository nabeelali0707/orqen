import argparse
import asyncio
import json
import runpy
from pathlib import Path

import pytest

NAMESPACE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/benchmark_agentarch.py")
)
evaluate = NAMESPACE["evaluate"]


def test_preview_freezes_protocol_without_loading_grader_or_contacting_model(tmp_path, monkeypatch):
    class Dataset:
        provenance = {"revision": "fixture"}

        def __init__(self, *args):
            pass

        def cases(self):
            return ({"id": "2", "goal": "PRIVATE_TASK_TEXT"},)

    def forbidden(*args, **kwargs):
        raise AssertionError("Preview attempted grading or inference")

    monkeypatch.setitem(evaluate.__globals__, "AgentArchDataset", Dataset)
    monkeypatch.setitem(evaluate.__globals__, "official_grader", forbidden)
    monkeypatch.setitem(evaluate.__globals__, "model_identity", forbidden)
    args = argparse.Namespace(
        checkout=tmp_path,
        use_case="requesting_time_off",
        cases=["2"],
        modes=["whole_plan", "observed"],
        repetitions=1,
        seed=0,
        model="offline",
        max_calls=8,
        max_planner_calls=4,
        timeout=300,
        request_timeout=120,
        negative_control=False,
        run_local=False,
        output=tmp_path / "preview.json",
    )
    report = asyncio.run(evaluate(args))
    assert report["network_requests"] == 0 and report["scheduled_runs"] == 2
    assert report["completed_runs"] == 0 and report["report_status"] == "preview"
    assert "PRIVATE_TASK_TEXT" not in json.dumps(report)
    args.cases = ["2", "2"]
    with pytest.raises(ValueError, match="unique"):
        asyncio.run(evaluate(args))
