import asyncio
import json
import subprocess
import sys

import httpx

from orqen.demo import run_ollama_demo
from orqen.providers.ollama import OllamaConfig


def test_demo_executes_model_proposal_and_records_usage_without_prompt():
    response = {
        "kind": "tools",
        "steps": [
            {
                "id": "sum",
                "tool": "add",
                "depends_on": [],
                "arguments": {"a": {"literal": 2}, "b": {"literal": 3}},
            }
        ],
    }
    mock = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "done": True,
                "message": {"content": json.dumps(response)},
                "prompt_eval_count": 99,
                "eval_count": 21,
            },
        )
    )
    report = asyncio.run(run_ollama_demo(OllamaConfig("offline-test"), http_transport=mock))
    assert report["passed"] and report["trace"]["calls"] == 1
    assert report["provider"]["requests"][0]["output_tokens"] == 21
    assert "Name the tool step" not in json.dumps(report)


def test_direct_answer_does_not_pass_a_required_tool_demo():
    mock = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "done": True,
                "message": {"content": '{"kind":"direct","result":5}'},
            },
        )
    )
    report = asyncio.run(run_ollama_demo(OllamaConfig("offline-test"), http_transport=mock))
    assert not report["passed"] and report["trace"]["calls"] == 0


def test_offline_failure_still_produces_a_report():
    def handler(request):
        raise httpx.ConnectError("PRIVATE_ERROR")

    report = asyncio.run(
        run_ollama_demo(OllamaConfig("offline-test"), http_transport=httpx.MockTransport(handler))
    )
    assert not report["passed"] and report["trace"]["failure"] == "planner_transport_error"
    assert "PRIVATE_ERROR" not in json.dumps(report)


def test_cli_dry_run_has_no_requests_and_does_not_write_report(tmp_path):
    path = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "orqen.cli",
            "demo-ollama",
            "--model",
            "offline-test",
            "--dry-run",
            "--output",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["network_requests"] == 0 and report["provider"]["requests"] == []
    assert not path.exists()


def test_cli_bad_settings_fail_without_request():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "orqen.cli",
            "demo-ollama",
            "--model",
            "offline-test",
            "--timeout",
            "0",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
