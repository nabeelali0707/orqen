import json
import sys

import httpx
import pytest

from orqen.cli import main
from orqen.evaluation import write_report


def test_failed_atomic_replace_preserves_previous_report(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    write_report({"completed": 1}, path)

    def failure(*args):
        raise OSError("Disk error")

    monkeypatch.setattr("orqen.evaluation.os.replace", failure)
    with pytest.raises(OSError):
        write_report({"completed": 2}, path)
    assert json.loads(path.read_text()) == {"completed": 1}
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_report_does_not_overwrite_checkpoint(tmp_path):
    path = tmp_path / "report.json"
    write_report({"completed": 1}, path)
    with pytest.raises(ValueError):
        write_report({"value": float("nan")}, path)
    assert json.loads(path.read_text()) == {"completed": 1}


def test_model_schedule_preview_never_connects(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network client")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "orqen",
            "evaluate-model",
            "--model",
            "offline",
            "--dry-run",
            "--repetitions",
            "1",
            "--variants",
            "baseline",
            "proposal_review",
            "--faults",
            "none",
            "--output",
            str(output),
        ],
    )
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["scheduled_runs"] == 2 and report["max_planning_calls"] == 3
    assert report["network_requests"] == 0 and not output.exists()
