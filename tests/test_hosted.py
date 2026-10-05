import asyncio
import json

import httpx
import pytest

from orqen.demo import run_hosted_demo
from orqen.planning import PlanningRequest
from orqen.providers.common import ProviderError
from orqen.providers.hosted import HostedConfig, HostedTransport, load_api_key

REQUEST = PlanningRequest("PRIVATE_GOAL", (), {"type": "object"})
KEY = "unit-test-credential-not-a-real-key"
PROVIDERS = ("mistral", "openrouter")


def reply(content='{"kind":"direct","result":5}', **changes):
    return {
        "model": "test-model",
        "provider": "test-endpoint",
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": content}}
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 10},
        **changes,
    }


def transport(handler, provider="mistral", **config):
    return HostedTransport(
        HostedConfig(provider, "test-model", **config),
        api_key=KEY,
        allow_live=True,
        http_transport=httpx.MockTransport(handler),
    )


@pytest.mark.parametrize("provider", PROVIDERS)
def test_provider_wire_contract_and_redacted_metadata(provider):
    received = []

    def handler(request):
        received.append(request)
        return httpx.Response(200, json=reply())

    adapter = transport(handler, provider, seed=23)
    asyncio.run(adapter(REQUEST))
    request = received[0]
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert (
        str(request.url)
        == (
            {
                "mistral": "https://api.mistral.ai/v1/chat/completions",
                "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            }[provider]
        )
    )
    payload = json.loads(request.content)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["stream"] is False and payload["max_tokens"] == 512
    assert payload["random_seed" if provider == "mistral" else "seed"] == 23
    if provider == "openrouter":
        assert payload["provider"] == {
            "require_parameters": True,
            "allow_fallbacks": False,
            "data_collection": "deny",
        }
    metadata = adapter.metadata()
    assert metadata["requests"][0]["input_tokens"] == 12
    assert metadata["requests"][0]["output_tokens"] == 10
    assert metadata["estimated_cost"] is None
    assert KEY not in json.dumps(metadata) + repr(adapter)
    assert "PRIVATE_GOAL" not in json.dumps(metadata)


def test_requests_disabled_by_default_even_with_credentials():
    called = []
    adapter = HostedTransport(
        HostedConfig("mistral", "test"),
        api_key=KEY,
        http_transport=httpx.MockTransport(lambda r: called.append(r)),
    )
    with pytest.raises(ProviderError, match="disabled"):
        asyncio.run(adapter(REQUEST))
    assert not called and not adapter.records


@pytest.mark.parametrize("status", [301, 307, 401, 403, 429, 500, 503])
@pytest.mark.parametrize("provider", PROVIDERS)
def test_errors_never_retry_redirect_or_include_body(provider, status):
    called = []

    def handler(request):
        called.append(request)
        return httpx.Response(status, text=KEY, headers={"Location": "https://example.invalid"})

    adapter = transport(handler, provider)
    with pytest.raises(ProviderError) as error:
        asyncio.run(adapter(REQUEST))
    assert len(called) == 1
    assert KEY not in str(error.value) + json.dumps(adapter.metadata())
    with pytest.raises(ProviderError, match="budget"):
        asyncio.run(adapter(REQUEST))
    assert len(called) == 1


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"error": {"message": KEY}},
        reply(choices=[]),
        reply(choices=[{}, {}]),
        reply(
            choices=[{"finish_reason": "length", "message": {"role": "assistant", "content": "{}"}}]
        ),
        reply(
            choices=[{"finish_reason": "stop", "message": {"role": "assistant", "content": None}}]
        ),
        reply(
            choices=[
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "{}", "tool_calls": [{}]},
                }
            ]
        ),
        reply(
            choices=[
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "{}", "refusal": "denied"},
                }
            ]
        ),
        reply(KEY),
    ],
)
def test_rejects_incomplete_refused_or_nontext_responses(document):
    adapter = transport(lambda _: httpx.Response(200, json=document))
    with pytest.raises(ProviderError) as error:
        asyncio.run(adapter(REQUEST))
    assert KEY not in str(error.value) + json.dumps(adapter.metadata())


def test_unknown_usage_is_not_counted_as_zero_and_echoed_key_is_not_metadata():
    adapter = transport(
        lambda _: httpx.Response(
            200,
            json=reply(
                usage={"prompt_tokens": True, "completion_tokens": -3}, model=KEY, provider=KEY
            ),
        )
    )
    asyncio.run(adapter(REQUEST))
    record = adapter.records[0]
    assert record["input_tokens"] is None and record["output_tokens"] is None
    assert record["returned_model"] is None and record["routed_provider"] is None


def test_request_and_response_bytes_are_bounded():
    called = []
    adapter = transport(lambda r: called.append(r), max_request_bytes=1)
    with pytest.raises(ProviderError, match="request exceeded"):
        asyncio.run(adapter(REQUEST))
    assert not called
    adapter = transport(lambda _: httpx.Response(200, content=b"x" * 100), max_response_bytes=50)
    with pytest.raises(ProviderError, match="response exceeded"):
        asyncio.run(adapter(REQUEST))


def test_deadline_and_connection_errors_are_redacted():
    async def slow(request):
        await asyncio.sleep(1)

    adapter = transport(slow, timeout_seconds=0.01)
    with pytest.raises(ProviderError, match="timed out"):
        asyncio.run(adapter(REQUEST))
    assert adapter.records[0]["status"] == "timeout"

    def fail(request):
        raise httpx.ConnectError(KEY)

    with pytest.raises(ProviderError) as error:
        asyncio.run(transport(fail)(REQUEST))
    assert KEY not in str(error.value)


def test_concurrent_calls_share_budget_and_cancellation_consumes_allowance():
    async def check():
        entered = asyncio.Event()

        async def wait(request):
            entered.set()
            await asyncio.Event().wait()

        adapter = transport(wait)
        running = asyncio.create_task(adapter(REQUEST))
        await entered.wait()
        with pytest.raises(ProviderError, match="budget"):
            await adapter(REQUEST)
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert adapter.records[0]["status"] == "cancelled"

    asyncio.run(check())


@pytest.mark.parametrize("provider", PROVIDERS)
def test_mocked_full_execution_passes_only_with_verified_tool_result(provider):
    plan = {
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
    mock = httpx.MockTransport(lambda _: httpx.Response(200, json=reply(json.dumps(plan))))
    report = asyncio.run(
        run_hosted_demo(
            HostedConfig(provider, "test"), api_key=KEY, allow_live=True, http_transport=mock
        )
    )
    assert report["passed"] and report["trace"]["planner_calls"] == 1
    assert report["trace"]["calls"] == 1
    direct = httpx.MockTransport(lambda _: httpx.Response(200, json=reply()))
    report = asyncio.run(
        run_hosted_demo(
            HostedConfig(provider, "test"), api_key=KEY, allow_live=True, http_transport=direct
        )
    )
    assert not report["passed"]


def test_explicit_credential_file_does_not_mutate_or_expand_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text(f'MISTRAL_API_KEY="{KEY}"\nOPENROUTER_API_KEY=other\n', encoding="utf-8")
    assert load_api_key("mistral", env_file=path, environ={}) == KEY
    assert (
        load_api_key("mistral", env_file=path, environ={"MISTRAL_API_KEY": "override"})
        == "override"
    )
    with pytest.raises(ValueError):
        load_api_key("mistral", environ={})
    path.write_text(f"MISTRAL_API_KEY={KEY}\nMISTRAL_API_KEY={KEY}\n", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_api_key("mistral", env_file=path, environ={})
    assert KEY not in str(error.value)


@pytest.mark.parametrize(
    "settings",
    [
        {"temperature": float("nan")},
        {"temperature": True},
        {"timeout_seconds": 0},
        {"max_requests": 0},
        {"seed": -1},
        {"max_output_tokens": False},
        {"model": "bad\nmodel"},
        {"provider": "unknown"},
        {"routing_provider": "custom"},
    ],
)
def test_invalid_settings_fail_before_requests(settings):
    with pytest.raises(ValueError):
        HostedConfig(**{"provider": "mistral", "model": "test", **settings})
