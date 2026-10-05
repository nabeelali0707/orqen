"""Bounded Mistral/OpenRouter chat transports, disabled until explicitly enabled."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ..planning import PlanningRequest
from .common import INSTRUCTIONS, ProviderError

ENDPOINTS = {
    "mistral": "https://api.mistral.ai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}
KEY_VARIABLES = {"mistral": "MISTRAL_API_KEY", "openrouter": "OPENROUTER_API_KEY"}


def _valid_key(value: Any) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 4096
        and all(33 <= ord(character) <= 126 for character in value)
    )


def load_api_key(
    provider: str, *, env_file: Path | None = None, environ: Mapping[str, str] | None = None
) -> str:
    """Read one key; process environment takes precedence over an explicit file.

    The file supports KEY=value, comments and optional matching quotes only. No
    interpolation, execution, searching parent directories or environment mutation.
    """
    if provider not in KEY_VARIABLES:
        raise ValueError("Unknown provider")
    name = KEY_VARIABLES[provider]
    environment = os.environ if environ is None else environ
    value = environment.get(name)
    if value is None and env_file is not None:
        try:
            with Path(env_file).open("rb") as source:
                raw = source.read(32769)
            if len(raw) > 32768:
                raise ValueError
            found = []
            for line in raw.decode("utf-8-sig").splitlines():
                field, separator, item = line.strip().partition("=")
                if separator and field.strip() == name:
                    item = item.strip()
                    if len(item) >= 2 and item[0] in {"'", '"'} and item[-1] == item[0]:
                        item = item[1:-1]
                    found.append(item)
            if len(found) != 1:
                raise ValueError
            value = found[0]
        except (OSError, ValueError, UnicodeError):
            raise ValueError(
                "Credential file is unreadable or has a missing/duplicate key"
            ) from None
    if not _valid_key(value):
        raise ValueError("The selected provider credential is missing or invalid")
    return value


@dataclass(frozen=True)
class HostedConfig:
    provider: str
    model: str
    temperature: float = 0.0
    seed: int = 0
    max_output_tokens: int = 512
    timeout_seconds: float = 60.0
    max_request_bytes: int = 65536
    max_response_bytes: int = 1048576
    max_requests: int = 1
    routing_provider: str | None = None

    def __post_init__(self) -> None:
        if self.provider not in ENDPOINTS:
            raise ValueError("Provider must be mistral or openrouter")
        for value in (self.model, self.routing_provider):
            if value is not None and (
                type(value) is not str
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", value)
            ):
                raise ValueError("Invalid model or routing provider identifier")
        if self.model is None:
            raise ValueError("An explicit model identifier is required")
        if self.provider != "openrouter" and self.routing_provider is not None:
            raise ValueError("Provider routing is available only for OpenRouter")
        for name in (
            "seed",
            "max_output_tokens",
            "max_request_bytes",
            "max_response_bytes",
            "max_requests",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "seed" else 1):
                raise ValueError(f"Invalid {name}")
        for name in ("temperature", "timeout_seconds"):
            value = getattr(self, name)
            if type(value) not in {int, float} or not math.isfinite(value):
                raise ValueError(f"Invalid {name}")
        if not 0 <= self.temperature <= 1 or self.timeout_seconds <= 0:
            raise ValueError("Temperature must be 0-1 and timeout must be positive")


class HostedTransport:
    """Provider-specific wire options over fixed HTTPS endpoints.

    Keys are kept outside configuration and metadata. Each instance has its own
    request allowance. No retries, fallback requests, redirects or proxy lookup.
    Instantiate a fresh transport per run. JSONPlanner must validate its output.
    """

    def __init__(
        self,
        config: HostedConfig,
        *,
        api_key: str | None = None,
        allow_live: bool = False,
        http_transport: Any = None,
    ) -> None:
        if type(allow_live) is not bool:
            raise ValueError("allow_live must be a bool")
        if api_key is not None and not _valid_key(api_key):
            raise ValueError("Provider credential is invalid")
        self.config = config
        self._api_key = api_key
        self.allow_live = allow_live
        self.http_transport = http_transport
        self.records: list[dict[str, Any]] = []
        self._requests_started = 0

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.config.provider,
            "settings": asdict(self.config),
            "endpoint": ENDPOINTS[self.config.provider],
            "response_format": "json_object",
            "instruction_sha256": hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
            "requests": [dict(record) for record in self.records],
            "estimated_cost": None,
        }

    async def __call__(self, request: PlanningRequest) -> str:
        if not self.allow_live:
            raise ProviderError("Live provider requests are disabled")
        if self._api_key is None:
            raise ProviderError("Provider credential is not configured")
        if self._requests_started >= self.config.max_requests:
            raise ProviderError("Provider request budget exhausted")
        import httpx

        config = self.config
        payload = {
            "model": config.model,
            "stream": False,
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": INSTRUCTIONS},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "goal": request.goal,
                            "catalog": request.catalog,
                            "response_schema": request.response_schema,
                        },
                        allow_nan=False,
                    ),
                },
            ],
        }
        if config.provider == "mistral":
            payload["random_seed"] = config.seed
        else:
            payload["seed"] = config.seed
            payload["provider"] = {
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
            }
            if config.routing_provider:
                payload["provider"]["only"] = [config.routing_provider]
        body = json.dumps(payload, allow_nan=False).encode()
        if len(body) > config.max_request_bytes:
            raise ProviderError("Provider request exceeded the byte limit")
        # Reserve before the first await, so concurrent calls cannot overspend this instance.
        self._requests_started += 1
        started = perf_counter()
        record = {
            "status": "error",
            "input_tokens": None,
            "output_tokens": None,
            "returned_model": None,
            "routed_provider": None,
            "elapsed_seconds": None,
        }
        self.records.append(record)
        try:
            async with asyncio.timeout(config.timeout_seconds):
                async with httpx.AsyncClient(
                    transport=self.http_transport,
                    timeout=config.timeout_seconds,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    async with client.stream(
                        "POST",
                        ENDPOINTS[config.provider],
                        content=body,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                    ) as response:
                        if response.status_code != 200:
                            record.update(status="http_error", http_status=response.status_code)
                            raise ProviderError("Provider returned an unsuccessful HTTP status")
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(raw) + len(chunk) > config.max_response_bytes:
                                raise ProviderError("Provider response exceeded the byte limit")
                            raw.extend(chunk)
            try:
                document = json.loads(raw)
            except (ValueError, UnicodeError, RecursionError):
                raise ProviderError("Provider response was not valid JSON") from None
            if type(document) is not dict or "error" in document:
                raise ProviderError("Provider returned an invalid response")
            usage = document.get("usage")
            if isinstance(usage, dict):
                for field, target in (
                    ("prompt_tokens", "input_tokens"),
                    ("completion_tokens", "output_tokens"),
                ):
                    value = usage.get(field)
                    if type(value) is int and value >= 0:
                        record[target] = value
            for field, target in (("model", "returned_model"), ("provider", "routed_provider")):
                value = document.get(field)
                if type(value) is str and len(value) <= 200 and self._api_key not in value:
                    record[target] = value
            choices = document.get("choices")
            if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
                raise ProviderError("Provider returned an invalid choice count")
            choice = choices[0]
            message = choice.get("message")
            if (
                choice.get("finish_reason") != "stop"
                or type(message) is not dict
                or message.get("role") != "assistant"
                or message.get("refusal")
                or message.get("tool_calls")
                or message.get("function_call")
                or type(message.get("content")) is not str
                or not message["content"].strip()
            ):
                raise ProviderError("Provider returned an incomplete or unsupported completion")
            if self._api_key in message["content"]:
                raise ProviderError("Provider response contains a credential")
            record["status"] = "ok"
            return message["content"]
        except (TimeoutError, httpx.TimeoutException):
            record["status"] = "timeout"
            raise ProviderError("Provider request timed out") from None
        except httpx.HTTPError:
            record["status"] = "connection_error"
            raise ProviderError("Provider connection failed") from None
        except asyncio.CancelledError:
            record["status"] = "cancelled"
            raise
        finally:
            record["elapsed_seconds"] = perf_counter() - started
