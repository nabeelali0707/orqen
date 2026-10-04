import asyncio
import json

import httpx
import pytest
from test_engine import make_tool

from orqen import Failure, JSONPlanner, Orchestrator, PlanningRequest, Task, ToolRegistry
from orqen.providers.ollama import OllamaConfig, OllamaTransport, ProviderError

REQUEST = PlanningRequest("PRIVATE_GOAL", (), {"type": "object"})


def reply(**changes):
    return {
        "done": True,
        "done_reason": "stop",
        "model": "test:fixed",
        "message": {"role": "assistant", "content": '{"kind":"direct","result":4}'},
        "prompt_eval_count": 20,
        "eval_count": 10,
        **changes,
    }


def transport(handler, **settings):
    return OllamaTransport(
        OllamaConfig("test:fixed", **settings), http_transport=httpx.MockTransport(handler)
    )


def test_payload_settings_and_metadata_are_reproducible_and_redacted():
    received = []

    def handler(request):
        received.append(request)
        return httpx.Response(200, json=reply())

    adapter = transport(handler, seed=42, max_output_tokens=128, context_tokens=4096)
    assert asyncio.run(adapter(REQUEST)) == '{"kind":"direct","result":4}'
    payload = json.loads(received[0].content)
    assert received[0].url == "http://127.0.0.1:11434/api/chat"
    assert payload["stream"] is False and payload["format"] == REQUEST.response_schema
    assert payload["options"] == {
        "temperature": 0.0,
        "seed": 42,
        "num_predict": 128,
        "num_ctx": 4096,
    }
    record = adapter.metadata()
    assert record["requests"][0]["input_tokens"] == 20
    assert record["requests"][0]["output_tokens"] == 10
    assert record["estimated_cost"] is None
    assert "PRIVATE_GOAL" not in json.dumps(record)
    assert '"result"' not in json.dumps(record)


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_http_errors_do_not_retry_redirect_or_expose_response(status):
    called = []

    def handler(request):
        called.append(request.url)
        return httpx.Response(
            status, text="PRIVATE_SERVER_SECRET", headers={"Location": "https://example.com"}
        )

    adapter = transport(handler)
    with pytest.raises(ProviderError) as error:
        asyncio.run(adapter(REQUEST))
    assert len(called) == 1 and "PRIVATE_SERVER_SECRET" not in str(error.value)
    assert adapter.records[0]["status"] == "http_error"


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"error": "PRIVATE_ERROR"},
        reply(done=False),
        reply(done_reason="length"),
        reply(message={"content": 4}),
        reply(message={"content": "{}", "tool_calls": [{}]}),
    ],
)
def test_invalid_or_truncated_responses_are_rejected(document):
    adapter = transport(lambda request: httpx.Response(200, json=document))
    with pytest.raises(ProviderError):
        asyncio.run(adapter(REQUEST))
    assert adapter.records[0]["status"] != "ok"


def test_response_byte_limit_applies_before_parsing():
    adapter = transport(
        lambda request: httpx.Response(200, content=b"x" * 100), max_response_bytes=50
    )
    with pytest.raises(ProviderError, match="byte limit"):
        asyncio.run(adapter(REQUEST))


def test_missing_or_invalid_usage_is_unknown_not_zero():
    adapter = transport(
        lambda request: httpx.Response(200, json=reply(prompt_eval_count=True, eval_count=-1))
    )
    asyncio.run(adapter(REQUEST))
    assert adapter.records[0]["input_tokens"] is None
    assert adapter.records[0]["output_tokens"] is None


def test_timeout_is_bounded_and_recorded():
    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=reply())

    adapter = transport(handler, timeout_seconds=0.02)
    with pytest.raises(ProviderError, match="timed out"):
        asyncio.run(adapter(REQUEST))
    assert adapter.records[0]["status"] == "timeout"


def test_connection_error_is_redacted():
    def handler(request):
        raise httpx.ConnectError("PRIVATE_URL")

    adapter = transport(handler)
    with pytest.raises(ProviderError, match="connection failed") as error:
        asyncio.run(adapter(REQUEST))
    assert "PRIVATE_URL" not in str(error.value)


def test_transport_failure_has_distinct_executor_classification():
    adapter = transport(lambda request: httpx.Response(503))
    engine = Orchestrator(ToolRegistry((make_tool(),)), planner=JSONPlanner(adapter))
    result = asyncio.run(engine.run(Task("Double", lambda _: True)))
    assert result.failure == Failure.PLANNER and result.calls == 0 and result.planner_calls == 1


def test_generated_tool_plan_passes_through_executor():
    content = json.dumps(
        {
            "kind": "tools",
            "steps": [
                {
                    "id": "result",
                    "tool": "double",
                    "arguments": {"value": {"literal": 2}},
                    "depends_on": [],
                }
            ],
        }
    )
    adapter = transport(
        lambda request: httpx.Response(200, json=reply(message={"content": content}))
    )
    engine = Orchestrator(ToolRegistry((make_tool(),)), planner=JSONPlanner(adapter))
    result = asyncio.run(engine.run(Task("Double", lambda out: out["result"] == 4)))
    assert result.verified and result.calls == 1


@pytest.mark.parametrize(
    "settings",
    [
        {"base_url": "https://example.com"},
        {"base_url": "http://user:secret@localhost:11434"},
        {"base_url": "http://localhost:11434?key=secret"},
        {"base_url": "file:///tmp"},
        {"base_url": "http://example.com", "allow_remote": True},
        {"max_output_tokens": 0},
        {"seed": True},
        {"temperature": float("nan")},
        {"timeout_seconds": 0},
        {"max_response_bytes": -1},
    ],
)
def test_invalid_settings_are_rejected(settings):
    with pytest.raises(ValueError):
        OllamaConfig("test", **settings)


def test_cancellation_propagates_and_is_recorded():
    async def scenario():
        started = asyncio.Event()

        async def handler(request):
            started.set()
            await asyncio.sleep(10)

        adapter = transport(handler)
        running = asyncio.create_task(adapter(REQUEST))
        await started.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert adapter.records[0]["status"] == "cancelled"

    asyncio.run(scenario())
