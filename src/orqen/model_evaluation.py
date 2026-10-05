"""Small live-model ablations with independent tool outcome grading."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

from .engine import Orchestrator
from .models import Budget, Task, Tool, TransientToolError
from .multi_agent import ReviewPlanner
from .planning import JSONPlanner
from .providers.ollama import OllamaConfig, OllamaTransport, ProviderError
from .registry import ToolRegistry
from .retrieval import CatalogPolicy

VARIANTS = ("baseline", "retrieval", "no_recovery", "proposal_review")


def source_fingerprint() -> str:
    source = hashlib.sha256()
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        source.update(path.relative_to(Path(__file__).parent).as_posix().encode())
        source.update(path.read_bytes())
    return source.hexdigest()


def arithmetic_checks(outputs: dict, attempts: list) -> dict[str, bool]:
    """Diagnostic predicates for the synthetic fixture; never expose raw values."""
    return {
        "required_tool_called": bool(attempts),
        "correct_operands": bool(attempts) and all(args == (7, 4) for args in attempts),
        "exact_output_step": set(outputs) == {"sum"},
        "correct_value": list(outputs.values()) == [11],
    }


async def model_identity(config: OllamaConfig, *, http_transport: Any = None) -> dict:
    """Record installed model digest and server version without pulling a model."""
    import httpx

    async with asyncio.timeout(min(config.timeout_seconds, 15)):
        async with httpx.AsyncClient(
            transport=http_transport, trust_env=False, follow_redirects=False, timeout=15
        ) as client:
            documents = []
            for endpoint in ("version", "tags"):
                async with client.stream(
                    "GET", f"{config.base_url.rstrip('/')}/api/{endpoint}"
                ) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > config.max_response_bytes:
                            raise ProviderError("Model metadata exceeds response limit")
                    documents.append(json.loads(body))
    version, tags = documents
    matches = [m for m in tags["models"] if m.get("name") == config.model]
    if len(matches) != 1 or matches[0].get("remote_host"):
        raise ProviderError("Experiment requires an installed local model with an exact tag")
    model = matches[0]
    if not isinstance(model.get("digest"), str) or not model["digest"]:
        raise ProviderError("Model digest missing")
    return {
        "server_version": version["version"],
        "model": config.model,
        "digest": model["digest"],
        "details": model.get("details", {}),
    }


async def evaluate_models(
    config: OllamaConfig,
    *,
    repetitions: int = 2,
    seed: int = 0,
    http_transport: Any = None,
    variants: tuple[str, ...] = VARIANTS,
    faults: tuple[bool, ...] = (False, True),
) -> dict:
    if type(repetitions) is not int or not 1 <= repetitions <= 100:
        raise ValueError("repetitions must be between 1 and 100")
    if (
        not variants
        or len(set(variants)) != len(variants)
        or any(v not in VARIANTS for v in variants)
    ):
        raise ValueError("Choose unique supported variants")
    if not faults or any(type(f) is not bool for f in faults) or len(set(faults)) != len(faults):
        raise ValueError("Choose unique boolean fault conditions")
    initial_source = source_fingerprint()
    identity = await model_identity(config, http_transport=http_transport)
    schedule = [
        (variant, fault, trial)
        for trial in range(repetitions)
        for fault in faults
        for variant in variants
    ]
    random.Random(seed).shuffle(schedule)
    rows = []
    for variant, fault, trial in schedule:
        attempts = []

        async def add(a: int, b: int, *, attempts=attempts, fault=fault) -> int:
            attempts.append((a, b))
            if fault and len(attempts) == 1:
                raise TransientToolError("Injected read failure")
            return a + b

        async def multiply(a: int, b: int) -> int:
            return a * b

        schema = {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
            "additionalProperties": False,
        }
        registry = ToolRegistry(
            (
                Tool(
                    "add",
                    "Add two integers",
                    "math.add",
                    add,
                    schema,
                    {"type": "integer"},
                    read_only=True,
                ),
                Tool(
                    "multiply",
                    "Multiply two integers",
                    "math.multiply",
                    multiply,
                    schema,
                    {"type": "integer"},
                    read_only=True,
                ),
            )
        )
        settings = replace(config, seed=config.seed + trial)
        transports = [OllamaTransport(settings, http_transport=http_transport)]
        planner = JSONPlanner(transports[0], max_steps=1)
        if variant == "proposal_review":
            transports.append(OllamaTransport(settings, http_transport=http_transport))
            planner = ReviewPlanner(planner, JSONPlanner(transports[1], max_steps=1))
        budget = Budget(
            max_calls=2,
            max_steps=1,
            max_retries=1,
            max_planner_calls=2,
            timeout_seconds=config.timeout_seconds * 2 + 2,
        )
        result = await Orchestrator(
            registry,
            planner=planner,
            recovery=variant != "no_recovery",
            catalog_policy=CatalogPolicy("adaptive", 1) if variant == "retrieval" else None,
        ).run(
            Task(
                "Use add once to add 7 and 4. Name the output step sum.",
                lambda outputs, attempts=attempts: (
                    outputs == {"sum": 11}
                    and bool(attempts)
                    and all(args == (7, 4) for args in attempts)
                ),
            ),
            budget=budget,
        )
        rows.append(
            {
                "variant": variant,
                "transient_fault": fault,
                "trial": trial,
                "trace": result.trace(),
                "providers": [t.metadata() for t in transports],
                "checks": arithmetic_checks(result.outputs, attempts),
            }
        )
    final_identity = await model_identity(config, http_transport=http_transport)
    final_source = source_fingerprint()
    return {
        "schema_version": 1,
        "suite": "live-arithmetic-ablations-v1",
        "evidence": "Local synthetic model experiment; not AgentArch or held-out research evidence",
        "identity": identity,
        "identity_stable": identity == final_identity,
        "source_sha256": initial_source,
        "source_sha256_after": final_source,
        "source_stable": initial_source == final_source,
        "variants": list(variants),
        "faults": list(faults),
        "order_seed": seed,
        "repetitions": repetitions,
        "rows": rows,
        "summaries": [
            {
                "variant": v,
                "runs": sum(r["variant"] == v for r in rows),
                "verified": sum(r["variant"] == v and r["trace"]["verified"] for r in rows),
                "planner_calls": sum(
                    r["trace"]["planner_calls"] for r in rows if r["variant"] == v
                ),
            }
            for v in variants
        ],
    }
