# Structured planning and catalog retrieval

`JSONPlanner` connects an application-owned async generation function to Orqen's existing executor. It supplies a goal, offered tool metadata, and a response schema. The function returns JSON text. The core planner makes no provider request itself. An optional [Ollama transport](ollama.md) can supply the generation callback.

Run the offline integration example:

```powershell
.\.venv\isolated\Scripts\python.exe examples/structured_planner.py
```

## Integrate a generator

```python
from orqen import JSONPlanner, Orchestrator, PlanningRequest

async def generate(request: PlanningRequest) -> str:
    # Use your configured provider client here. Send request.goal,
    # request.catalog, and request.response_schema. Return the generated JSON.
    # Keep credentials and model settings in application code.
    raise NotImplementedError("Supply a model transport")

engine = Orchestrator(registry, planner=JSONPlanner(generate))
```

The integrating application must record model/version, prompt, sampling settings, token limits, usage, cost, and provider response identifiers for real experiments. Orqen currently records planner attempt counts and offered tool identifiers, not model tokens or monetary cost. A transport must not perform business actions during planning.

## Wire contract

A direct proposal is `{"kind":"direct","result":5}`. A tool proposal names only tools in the offered catalog:

```json
{
  "kind": "tools",
  "steps": [
    {
      "id": "customer",
      "tool": "customer_lookup",
      "arguments": {"customer_id": {"literal": "c-123"}},
      "depends_on": []
    },
    {
      "id": "route",
      "tool": "queue_selector",
      "arguments": {"tier": {"ref": {"step": "customer", "path": ["tier"]}}},
      "depends_on": []
    }
  ]
}
```

Each top-level argument is either a `literal` value or a `ref` to a whole previous result or nested field. Reference paths use string keys or nonnegative integer array indices. A literal can contain arbitrary JSON objects, including objects shaped like references; it is never interpreted as executable syntax. Nested references inside literal objects are not supported by this wire format. Use a reference to the complete object or construct it in a trusted tool.

The parser rejects extra control fields, duplicate JSON keys, nonfinite numbers, unknown tools, cyclic dependencies, malformed references, oversized responses, and all-literal calls whose input schema fails. It derives capabilities from the offered catalog and pins each call to the named tool. Calls containing references undergo full input validation after those references resolve. JSON Schema itself does not establish business correctness: executor permissions, preconditions, postconditions, and the task verifier remain authoritative.

Defaults: at most 20 proposed steps and 65,536 response bytes. The executor also enforces its own `Budget.max_steps`. The plan format does not accept permissions, handlers, verifier code, or a request to bypass validation.

## Catalog policies

`Orchestrator` defaults to the entire authorized, available catalog. `adaptive_tools` controls ordering of interchangeable tools during execution; it is separate from the new `catalog_policy`, which changes what the planner sees.

```python
from orqen import CatalogPolicy

engine = Orchestrator(
    registry,
    planner=JSONPlanner(generate),
    catalog_policy=CatalogPolicy(mode="adaptive", top_k=3),
)
```

Modes:

- `all`: preserve the complete authorized catalog in registration order.
- `fixed`: lexical overlap ranking, truncated to exactly `top_k` or the available catalog size.
- `adaptive`: retain positive matches up to the cutoff, including all cutoff ties; if no terms match, return the full catalog. The result can exceed `top_k` and is not a calibrated confidence estimate.

The lexical ranker uses names, descriptions, and capabilities. It cannot infer hidden business prerequisites. Keyword overlap is neither semantic equivalence nor authorization.

A JSON planner may return `{"kind":"expand_catalog"}` when information is missing. Before any tool runs, Orqen offers the full authorized catalog and asks for a new plan. Expansion happens at most once; another expansion request returns `no_matching_tool`. `Budget.max_planner_calls` defaults to two and can prevent the second call. No unauthorized or unavailable tool is added. There is no automatic execution retry based on a failed plan.

All planning time counts against the run deadline. `RunResult.planner_calls` counts attempts, including failures, separately from actual tool calls. `catalog_offered` events record tool IDs and attempt numbers; `catalog_expanded` records expansion. Raw goals, generated plans, and arguments stay out of default traces.

## Limits

The replay example and tests do not exercise a live model. There is no claim of improved reasoning, planning accuracy, or reduced model cost. Full plans are generated before each stage executes; `WorkflowRunner` supports application-owned branching between stages. A model could fail to notice a missing prerequisite and never request expansion. Keep the full catalog default until application-specific evidence supports filtering.

## Application-owned step identifiers

When a workflow requires exact internal output names, configure
`JSONPlanner(transport, max_steps=1, step_ids=("sum",))`. This optional contract
requires every listed step exactly once, excludes direct answers, and permits
catalog expansion. It constrains the generation schema and is independently
validated before execution. It never renames returned steps or repairs an invalid
plan. Omit it for open-ended plans whose step names are not application requirements.
This is a complete set of identifiers, not a subset: prerequisite steps must also
be listed. Tool choice, arguments, permissions and final grading remain separate.
