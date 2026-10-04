from jsonschema import Draft202012Validator

from orqen.planning import PlanningRequest, response_schema
from orqen.providers.ollama import provider_schema


def test_provider_grammar_rejects_empty_objects_as_integer_literals():
    catalog = (
        {
            "name": "add",
            "input_schema": {
                "type": "object",
                "properties": {"a": {"type": "integer"}},
                "required": ["a"],
                "additionalProperties": False,
            },
        },
    )
    schema = provider_schema(PlanningRequest("test", catalog, response_schema()))
    validator = Draft202012Validator(schema)
    plan = {
        "kind": "tools",
        "steps": [
            {"id": "sum", "tool": "add", "depends_on": [], "arguments": {"a": {"literal": {}}}}
        ],
    }
    assert not validator.is_valid(plan)
    plan["steps"][0]["arguments"]["a"]["literal"] = 2
    assert validator.is_valid(plan)
