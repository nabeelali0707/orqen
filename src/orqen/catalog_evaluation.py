"""Tool coverage measurement, deliberately separate from task-success claims."""

from __future__ import annotations

import hashlib
import json
import statistics
from copy import deepcopy
from importlib.resources import files
from time import perf_counter
from typing import Any

from .registry import ResultValidator
from .retrieval import CatalogPolicy


def default_dataset() -> dict[str, Any]:
    return json.loads(files("orqen").joinpath("data/catalog-regression.json").read_text("utf-8"))


def evaluate_catalog(dataset: dict[str, Any]) -> dict[str, Any]:
    schema = {
        "type": "object",
        "required": ["name", "tools", "queries"],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "tools": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name", "description", "capability"],
                    "properties": {
                        name: {"type": "string", "minLength": 1}
                        for name in ("name", "description", "capability")
                    },
                },
            },
            "queries": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "goal", "required_tools"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "goal": {"type": "string"},
                        "required_tools": {
                            "type": "array",
                            "minItems": 1,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        },
    }
    if not ResultValidator.matches(schema, dataset):
        raise ValueError("Dataset does not satisfy the catalog evaluation schema")
    names = [tool["name"] for tool in dataset["tools"]]
    ids = [query["id"] for query in dataset["queries"]]
    if len(set(names)) != len(names) or len(set(ids)) != len(ids):
        raise ValueError("Tool names and query identifiers must be unique")
    if any(not set(query["required_tools"]) <= set(names) for query in dataset["queries"]):
        raise ValueError("Ground truth contains a tool absent from the catalog")
    policies = {
        "all": CatalogPolicy(),
        "fixed_1": CatalogPolicy("fixed", 1),
        "fixed_3": CatalogPolicy("fixed", 3),
        "adaptive_3": CatalogPolicy("adaptive", 3),
    }
    rows = []
    for name, policy in policies.items():
        for query in dataset["queries"]:
            started = perf_counter()
            # Ground truth is passed only to the grader, never the retriever.
            selected = policy.select(query["goal"], tuple(deepcopy(dataset["tools"])))
            elapsed = perf_counter() - started
            candidates = [tool["name"] for tool in selected]
            required = set(query["required_tools"])
            missing = sorted(required - set(candidates))
            rows.append(
                {
                    "policy": name,
                    "query": query["id"],
                    "candidates": candidates,
                    "required_count": len(required),
                    "covered_count": len(required) - len(missing),
                    "missing": missing,
                    "complete_coverage": not missing,
                    "catalog_bytes": len(json.dumps(selected, ensure_ascii=False).encode("utf-8")),
                    "elapsed_seconds": elapsed,
                }
            )
    summaries = {}
    for name in policies:
        group = [row for row in rows if row["policy"] == name]
        summaries[name] = {
            "queries": len(group),
            "complete_coverage_count": sum(row["complete_coverage"] for row in group),
            "complete_coverage_rate": sum(row["complete_coverage"] for row in group) / len(group),
            "required_tool_recall": sum(row["covered_count"] for row in group)
            / sum(row["required_count"] for row in group),
            "mean_tools_offered": statistics.mean(len(row["candidates"]) for row in group),
            "mean_catalog_bytes": statistics.mean(row["catalog_bytes"] for row in group),
            "median_retrieval_seconds": statistics.median(row["elapsed_seconds"] for row in group),
        }
    return {
        "schema_version": 1,
        "suite": dataset["name"],
        "dataset_sha256": hashlib.sha256(json.dumps(dataset, sort_keys=True).encode()).hexdigest(),
        "evidence": "Offline required-tool coverage only; not task success or model performance",
        "summaries": summaries,
        "rows": rows,
        "limitations": [
            "The bundled dataset is visible during development and has only eight queries.",
            "Retrieval sees goal and catalog only; required tools are independent labels.",
            "Coverage is necessary but does not establish correct arguments or execution.",
            "An ambiguous query may need clarification even if every required tool is present.",
            "Catalog bytes are UTF-8 metadata size, not model tokens or monetary cost.",
            "This measures the first shortlist, before any planner-requested expansion.",
        ],
    }
