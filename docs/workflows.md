# Observation-driven workflows

`WorkflowRunner` lets trusted application code choose a new `Task` after each
verified stage. Each stage uses the existing `Orchestrator`, including its planner,
catalog policy, permissions, confirmations, contracts and read recovery. This is
conditional application control flow; it does not establish adaptive reasoning.

```python
from orqen import Budget, WorkflowRunner

# Each function below is application-owned, not model-generated code.
async def next_task(observations):
    if not observations:
        return make_inspection_task()
    if len(observations) == 1:
        return make_action_task(observations[0])
    return None

result = await WorkflowRunner(orchestrator).run(
    next_task,
    verify_business_outcome,
    access=application_access,
    budget=Budget(max_calls=4, max_steps=4, max_planner_calls=2),
    max_stages=2,
)
```

The selection callback receives defensive copies of previous stage outputs. It
returns a task or `None`. Returning `None` triggers an independent final verifier;
successful stages alone do not imply successful business completion. Selection
and verification may be synchronous or async. These trusted callbacks must not
perform business writes: effects belong in registered tools so they are tracked.

Tool calls, proposed steps, planning calls and elapsed time share one budget across
stages. `max_retries` retains the executor's per-tool-call meaning. `max_stages`
also bounds direct-response loops. The selector is called at most `max_stages + 1`
times, including its final stop decision. Step identifiers and `Ref` values are
local to a stage; supply prior observations as arguments to a subsequent task.

A failed, blocked or uncertain stage stops the workflow immediately. No stage is
automatically replayed. Failure after any attempted write sets
`requires_reconciliation`, including a later stage being blocked. A selection or
verification exception after writes is classified as uncertain. Cancellation
propagates to the caller; persist an uncertain execution record at the service
boundary before attempting reconciliation. This runner is not a durable scheduler.

`result.trace()` exports metadata only; outputs stay in the in-memory stage
results. Application callbacks and tools are trusted Python code, not a sandbox.
They must cooperate with cancellation. No in-process timeout can forcibly stop a
blocking synchronous function or undo a side effect. For production use, configure
tool-side deadlines, backend idempotency and independently recorded write outcomes.
