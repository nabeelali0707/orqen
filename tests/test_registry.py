import pytest
from test_engine import INPUT, make_tool

from orqen import Budget, ResultValidator, ToolRegistry


def test_duplicate_tools_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        ToolRegistry((make_tool(), make_tool()))


def test_synchronous_handlers_are_rejected():
    with pytest.raises(TypeError, match="async"):
        ToolRegistry((make_tool(handler=lambda value: value),))


def test_schema_is_defensively_copied():
    registry = ToolRegistry((make_tool(),))
    registry.get("double").input_schema["required"].append("secret")
    assert registry.get("double").input_schema["required"] == ["value"]
    assert INPUT["required"] == ["value"]


def test_external_schema_refs_are_rejected():
    with pytest.raises(ValueError, match="local"):
        ToolRegistry((make_tool(output_schema={"$ref": "https://example.org/schema"}),))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "bad"}, (1, 2), object()])
def test_non_json_outputs_are_rejected(value):
    assert not ResultValidator.matches({}, value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_calls": -1},
        {"max_calls": True},
        {"max_retries": 1.5},
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
        {"retry_delay_seconds": -1},
    ],
)
def test_invalid_budgets_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Budget(**kwargs)
