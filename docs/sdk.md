# Python SDK

Requires Python 3.11 or newer. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe examples/customer_workflow.py
.\.venv\Scripts\python.exe -m pytest -q
```

On macOS or Linux, use `.venv/bin/python` instead.

## Define a tool and task

```python
import asyncio
from orqen import Orchestrator, Plan, Step, Task, Tool, ToolRegistry

async def add(a: int, b: int) -> int:
    return a + b

tool = Tool(
    name="add",
    description="Add two integers",
    capability="math.add",
    handler=add,
    input_schema={
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
        "additionalProperties": False,
    },
    output_schema={"type": "integer"},
    read_only=True,
)
task = Task(
    goal="Add 2 and 3",
    plan=Plan((Step("sum", "math.add", {"a": 2, "b": 3}),)),
    verify=lambda outputs: outputs["sum"] == 5,
)
result = asyncio.run(Orchestrator(ToolRegistry((tool,))).run(task))
assert result.verified
print(result.outputs)
```

## Dependencies and verification

Use `Ref("customer", ("tier",))` to pass a previous step's output field into another call. References create dependency edges automatically. Use `depends_on=("customer",)` for ordering without data flow. The executor rejects cycles and missing dependencies before invoking any tools.

Every task requires an application-owned `verify` callback. It receives all validated outputs and must return the literal boolean `True` to establish success. The callback may be async to read independent state. It should be read-only and avoid blocking the event loop. Output schema validation is separate from business verification.

## Permissions and recovery

Tools declare `permissions`, `read_only`, and `requires_confirmation`. `read_only` defaults to `False`: explicitly opt safe reads into retries. Provide `Access(permissions=frozenset(...), confirmed_tools=frozenset(...))` from trusted application code. A planner cannot grant access. Confirmation is supplied by the integrating application; Orqen does not show an approval UI. Tool-wide confirmation is suitable only when the application intentionally authorizes every invocation of that tool; use a precondition for argument-specific approval.

Optional `precondition(arguments, access)` and `postcondition(arguments, output)` callbacks may be sync or async and must return literal `True`. Preconditions run after schema validation and before each attempt, including retries. Postconditions run after output validation and before any dependent step receives that output. Exceptions fail closed, and callbacks receive copies so they cannot change executed arguments. A failed write postcondition produces `unknown` and is never retried automatically.

Use preconditions for resource-level authorization, business limits, or approvals bound to specific arguments. Postconditions can read independent state to confirm a change. Checks are not atomic with a remote write: enforce critical constraints and conditional updates in the backend as well. All callback time counts against the run deadline.

Only read-only calls that time out or raise `TransientToolError` can be retried. Configure `Budget` to bound calls, steps, retries per step, total time, and retry backoff. Writes are never replayed automatically. A write exception or malformed write result yields `unknown`, requiring application-level reconciliation.

An unavailable unpinned tool can fall back to another registered tool in the same capability. Capability names must identify interchangeable business semantics, not broad topics such as `database`. Permission denial, invalid arguments, and business verification failures do not trigger fallback.

## Model adapters and current limits

You can supply a `Planner` implementing `async plan(goal, catalog) -> Plan`, or supply a plan explicitly. The catalog contains authorized available tool metadata and schemas. Returned plans still pass through the same executor checks. No model provider is bundled in the first milestone; the included examples and policies are deterministic.

Task analysis currently derives complexity and dependencies from the supplied/generated plan and accepts an application-provided risk hint. It does not infer reliable business risk from natural language. Strategy selection chooses direct, function calling, or plan-and-execute according to the plan. Multi-agent execution is explicitly unsupported.

These strategy labels currently use the same sequential executor. They are not separate reasoning algorithms and must not be advertised as evidence of adaptive reasoning. Lexical tool ranking operates within an explicit capability; it does not reduce the catalog shown to the planner. See the [independent research review](research-review.md).

Tool handlers must be async and cooperate with cancellation. `asyncio` timeouts cannot kill blocking code or roll back remote actions. Use adapter-native network deadlines and an isolated worker for untrusted or blocking execution. An external cancellation propagates to the caller; reconcile any in-flight write before resubmission.

JSON Schema Draft 2020-12 is used without network schema references. Format annotations such as `email` are not asserted; encode required constraints explicitly or use application checks. Tool outputs must be JSON-compatible, finite values. No automatic argument coercion occurs.

## Results and traces

`RunResult` includes status, failure category, partial outputs, strategy, calls, retries, duration, and verification status. Cost is `None` until a model integration provides measured usage and pricing.

`result.trace()` excludes the task text, arguments, outputs, and exception messages. Tool and step identifiers remain in metadata, so choose identifiers without personal data. `result.outputs` is intentionally available to the application and may contain sensitive data; do not log the entire result by default.
