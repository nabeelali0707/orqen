"""Tool definitions and local JSON Schema validation."""

from __future__ import annotations

import inspect
import math
from copy import deepcopy
from dataclasses import replace
from typing import Any

from jsonschema import Draft202012Validator

from .models import Tool


def _check_schema(schema: Any) -> None:
    Draft202012Validator.check_schema(schema)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"$ref", "$dynamicRef"} and not child.startswith("#"):
                    raise ValueError("Only local schema references are supported")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema)


class ToolRegistry:
    def __init__(self, tools: tuple[Tool, ...] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if not tool.name.strip() or not tool.capability.strip():
            raise ValueError("Tool name and capability are required")
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        if not (
            inspect.iscoroutinefunction(tool.handler)
            or inspect.iscoroutinefunction(getattr(tool.handler, "__call__", None))  # noqa: B004
        ):
            raise TypeError("Tool handlers must be async callables")
        if (
            isinstance(tool.timeout_seconds, bool)
            or not math.isfinite(tool.timeout_seconds)
            or tool.timeout_seconds <= 0
        ):
            raise ValueError("Tool timeout must be finite and positive")
        input_schema = deepcopy(dict(tool.input_schema))
        output_schema = deepcopy(dict(tool.output_schema))
        _check_schema(input_schema)
        _check_schema(output_schema)
        if input_schema.get("type") != "object":
            raise ValueError("Tool inputs must declare an object schema")
        self._tools[tool.name] = replace(
            tool,
            input_schema=input_schema,
            output_schema=output_schema,
            permissions=frozenset(tool.permissions),
        )

    def get(self, name: str) -> Tool:
        return self._copy(self._tools[name])

    def all(self) -> tuple[Tool, ...]:
        return tuple(self._copy(tool) for tool in self._tools.values())

    @staticmethod
    def _copy(tool: Tool) -> Tool:
        return replace(
            tool,
            input_schema=deepcopy(tool.input_schema),
            output_schema=deepcopy(tool.output_schema),
        )


class ResultValidator:
    @staticmethod
    def matches(schema: Any, value: Any) -> bool:
        # Check JSON-compatible values as well as schema constraints. NaN, tuples,
        # custom objects and non-string object keys are not tool wire values.
        def is_json(item: Any) -> bool:
            if item is None or type(item) in {str, bool, int}:
                return True
            if type(item) is float:
                return math.isfinite(item)
            if type(item) is list:
                return all(is_json(child) for child in item)
            if type(item) is dict:
                return all(type(k) is str and is_json(v) for k, v in item.items())
            return False

        try:
            return is_json(value) and Draft202012Validator(schema).is_valid(value)
        except Exception:
            return False
