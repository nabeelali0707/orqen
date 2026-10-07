"""Strict JSON boundary for user-supplied model transports; no provider dependency."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .models import Plan, Ref, Step
from .registry import ResultValidator
from .routing import ordered_steps


class CatalogExpansionRequested(Exception):
    """Planner cannot complete a plan with the offered tools; no tools have run."""


class PlanningTransportError(Exception):
    """A provider request failed, rather than returning an invalid plan."""


def response_schema(max_steps: int = 20, step_ids: tuple[str, ...] | None = None) -> dict[str, Any]:
    schema = {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "kind": {"const": "direct"},
                    "result": {},
                },
                "required": ["kind", "result"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"const": "expand_catalog"},
                },
                "required": ["kind"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"const": "tools"},
                    "steps": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": max_steps,
                        "items": {"$ref": "#/$defs/step"},
                    },
                },
                "required": ["kind", "steps"],
                "additionalProperties": False,
            },
        ],
        "$defs": {
            "argument": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {"literal": {}},
                        "required": ["literal"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "properties": {
                            "ref": {
                                "type": "object",
                                "properties": {
                                    "step": {"type": "string", "minLength": 1},
                                    "path": {
                                        "type": "array",
                                        "items": {
                                            "oneOf": [
                                                {"type": "string"},
                                                {"type": "integer", "minimum": 0},
                                            ]
                                        },
                                    },
                                },
                                "required": ["step", "path"],
                                "additionalProperties": False,
                            }
                        },
                        "required": ["ref"],
                        "additionalProperties": False,
                    },
                ]
            },
            "step": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "tool": {"type": "string", "minLength": 1},
                    "arguments": {
                        "type": "object",
                        "additionalProperties": {"$ref": "#/$defs/argument"},
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                        "uniqueItems": True,
                    },
                },
                "required": ["id", "tool", "arguments", "depends_on"],
                "additionalProperties": False,
            },
        },
    }
    if step_ids is not None:
        schema["$defs"]["step"]["properties"]["id"] = {"enum": list(step_ids)}
        schema["oneOf"] = [
            branch
            for branch in schema["oneOf"]
            if branch["properties"]["kind"]["const"] != "direct"
        ]
        steps = schema["oneOf"][-1]["properties"]["steps"]
        steps["minItems"] = steps["maxItems"] = len(step_ids)
    return schema


@dataclass(frozen=True)
class PlanningRequest:
    goal: str
    catalog: tuple[dict[str, Any], ...]
    response_schema: dict[str, Any]


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON constant")


class JSONPlanner:
    """Turn structured generation into a validated plan pinned to offered tools.

    The transport owns provider credentials, model settings, and usage accounting.
    It must return JSON text and must not execute actions. There is no model call
    until the application supplies and invokes a real transport.
    """

    def __init__(
        self,
        generate: Callable[[PlanningRequest], Awaitable[str]],
        *,
        max_steps: int = 20,
        max_response_bytes: int = 65_536,
        step_ids: tuple[str, ...] | None = None,
    ) -> None:
        for value in (max_steps, max_response_bytes):
            if type(value) is not int or value < 1:
                raise ValueError("Planner limits must be positive integers")
        self.generate = generate
        self.max_steps = max_steps
        self.max_response_bytes = max_response_bytes
        if step_ids is not None:
            if (
                not isinstance(step_ids, (tuple, list))
                or not 1 <= len(step_ids) <= max_steps
                or any(
                    type(name) is not str or not name.strip() or name == "direct"
                    for name in step_ids
                )
                or len(set(step_ids)) != len(step_ids)
            ):
                raise ValueError("step_ids must contain unique non-reserved names within max_steps")
            step_ids = tuple(step_ids)
        self.step_ids = step_ids

    async def plan(self, goal: str, catalog: tuple[dict[str, Any], ...]) -> Plan:
        # The transport receives copies; mutating its prompt cannot authorize a tool.
        offered = {tool["name"]: deepcopy(tool) for tool in catalog}
        if len(offered) != len(catalog):
            raise ValueError("Duplicate catalog tool names")
        schema = response_schema(self.max_steps, self.step_ids)
        raw = await self.generate(PlanningRequest(goal, deepcopy(catalog), deepcopy(schema)))
        if type(raw) is not str or len(raw.encode("utf-8")) > self.max_response_bytes:
            raise ValueError("Planner response is not bounded JSON text")
        try:
            document = json.loads(raw, object_pairs_hook=_object, parse_constant=_reject_constant)
        except (ValueError, RecursionError) as exc:
            raise ValueError("Invalid planner JSON") from exc
        if not ResultValidator.matches(schema, document):
            raise ValueError("Planner response violates the wire contract")
        if document["kind"] == "expand_catalog":
            raise CatalogExpansionRequested
        if document["kind"] == "direct":
            return Plan(direct_result=document["result"])
        steps = []
        for item in document["steps"]:
            if item["tool"] not in offered:
                raise ValueError("Plan names a tool outside the offered catalog")
            tool = offered[item["tool"]]
            arguments = {}
            for key, value in item["arguments"].items():
                if "literal" in value:
                    arguments[key] = value["literal"]
                else:
                    reference = value["ref"]
                    path = reference["path"]
                    # JSON Schema accepts integral floats; Ref paths require actual ints.
                    if any(type(part) not in {str, int} for part in path):
                        raise ValueError("Reference path must contain strings or integer indices")
                    arguments[key] = Ref(reference["step"], tuple(path))
            if not any(isinstance(value, Ref) for value in arguments.values()):
                if not ResultValidator.matches(tool["input_schema"], arguments):
                    raise ValueError("Literal tool arguments violate the input schema")
            steps.append(
                Step(
                    item["id"],
                    tool["capability"],
                    arguments,
                    tool=item["tool"],
                    depends_on=tuple(item["depends_on"]),
                )
            )
        plan = Plan(tuple(steps))
        ordered_steps(plan, self.max_steps)
        return plan
