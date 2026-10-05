import asyncio
import json

import httpx
import pytest

from orqen.model_evaluation import arithmetic_checks, evaluate_models, model_identity
from orqen.providers.ollama import OllamaConfig, ProviderError


def handler(request):
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "test"})
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": "test", "digest": "abc"}]})
    return httpx.Response(
        200,
        json={
            "done": True,
            "message": {
                "content": json.dumps(
                    {
                        "kind": "tools",
                        "steps": [
                            {
                                "id": "sum",
                                "tool": "add",
                                "depends_on": [],
                                "arguments": {"a": {"literal": 7}, "b": {"literal": 4}},
                            }
                        ],
                    }
                )
            },
        },
    )


def test_factorial_runs_count_real_agent_calls_and_recovery_ablation():
    report = asyncio.run(
        evaluate_models(
            OllamaConfig("test"), repetitions=2, http_transport=httpx.MockTransport(handler)
        )
    )
    assert len(report["rows"]) == 16 and report["identity_stable"]
    summaries = {row["variant"]: row for row in report["summaries"]}
    assert summaries["baseline"]["verified"] == 4
    assert summaries["no_recovery"]["verified"] == 2
    assert summaries["proposal_review"]["planner_calls"] == 8
    assert "arguments" not in json.dumps(report)


def test_remote_model_alias_is_rejected_even_on_local_server():
    def remote(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "test", "digest": "x", "remote_host": "https://example.com"}
                    ]
                },
            )
        return handler(request)

    with pytest.raises(ProviderError):
        asyncio.run(
            model_identity(OllamaConfig("test"), http_transport=httpx.MockTransport(remote))
        )


def test_diagnostics_separate_correct_arithmetic_from_naming_and_tool_omission():
    renamed = arithmetic_checks({"sum_step": 11}, [(7, 4)])
    assert renamed == {
        "required_tool_called": True,
        "correct_operands": True,
        "exact_output_step": False,
        "correct_value": True,
    }
    direct = arithmetic_checks({"direct": 11}, [])
    assert direct["correct_value"] and not direct["required_tool_called"]
    assert not arithmetic_checks({"sum": 11}, [(8, 3)])["correct_operands"]


def test_wrong_output_name_still_fails_original_grader():
    def renamed(request):
        response = handler(request)
        if request.url.path == "/api/chat":
            body = response.json()
            plan = json.loads(body["message"]["content"])
            plan["steps"][0]["id"] = "sum_step"
            body["message"]["content"] = json.dumps(plan)
            return httpx.Response(200, json=body)
        return response

    report = asyncio.run(
        evaluate_models(
            OllamaConfig("test"),
            repetitions=1,
            variants=("baseline",),
            faults=(False,),
            http_transport=httpx.MockTransport(renamed),
        )
    )
    row = report["rows"][0]
    assert not row["trace"]["verified"]
    assert row["checks"]["correct_value"] and not row["checks"]["exact_output_step"]
    assert report["source_stable"]


def test_source_change_invalidates_reproducibility(monkeypatch):
    snapshots = iter(("before", "after"))
    monkeypatch.setattr("orqen.model_evaluation.source_fingerprint", lambda: next(snapshots))
    report = asyncio.run(
        evaluate_models(
            OllamaConfig("test"),
            repetitions=1,
            variants=("baseline",),
            faults=(False,),
            http_transport=httpx.MockTransport(handler),
        )
    )
    assert not report["source_stable"]
