import asyncio
import json

import httpx
import pytest

from orqen.model_evaluation import evaluate_models, model_identity
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
