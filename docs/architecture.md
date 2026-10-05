# Architecture proposal

## Core boundary

The Python SDK mediates between an application, a model adapter, and registered tools. Core decisions and trace formats should remain independent of a model provider. An authenticated API, dashboard, and MCP stdio server now expose registered workflows through the same execution service.

The table describes the target design. The SDK implements explicit plans, metadata-based strategy labels, optional capability-constrained lexical tool ranking, validation, sequential async execution, action contracts, verification, and conservative read recovery. Natural-language risk analysis and learned retrieval remain future work. An opt-in proposal/review planner now makes two separate agent calls before central execution. The [independent review](research-review.md) supersedes assumptions that these modules each require a separate intelligent subsystem. See [the SDK guide](sdk.md) for exact behavior and limits.

| Component | Input | Output and responsibility |
| --- | --- | --- |
| TaskAnalyzer | Request and application constraints | Task type, complexity, dependencies, risk, missing information, completion conditions |
| StrategyRouter | Task analysis and execution budget | Supported strategy and an inspectable selection reason |
| ToolRegistry | Application-owned tool definitions | Names, descriptions, input/output schemas, permissions, availability, side-effect and idempotency metadata |
| ToolRouter | Task or current plan step and registry | Ranked tool candidates; expand retrieval when coverage is insufficient |
| Executor | Selected tool and validated arguments | Structured result or classified failure, bounded by execution policy |
| ResultValidator | Result and completion conditions | Verified success, explicit failure, or an unresolved outcome |
| RecoveryPolicy | Failure, prior attempts, remaining budget | Retry, re-route, request missing information, or escalate |
| EvaluationRecorder | Decisions, timings, outcomes | Redacted traces and measurable task-level metrics |

## Strategy policy

Begin with transparent rules. A direct response uses no tools. Function calling handles a bounded tool interaction. Plan-and-execute handles dependent steps with explicit intermediate results. The experimental proposal/review strategy invokes separate proposing and reviewing planners, counts both calls, and retains central execution checks. See model-experiments.md for its limits.

Do not silently label sequential calls as multi-agent execution. Expose supported strategies explicitly, and report unsupported requests. Model recommendations do not grant permissions or bypass validation.

## Execution contract

Before invocation, check tool availability, schema validity, application permissions, required confirmation, and remaining call/time budgets. Validate outputs against their contracts, then evaluate task-specific postconditions. A syntactically valid response does not establish business success.

Application-owned tool preconditions execute before each attempt. Tool postconditions run before the result is released to dependent steps. Task verification then checks the overall goal. These checks share the run budget and fail closed. Omitted `read_only` metadata is treated as potentially state-changing, so safe retries require an explicit declaration. Neither model proposals nor retrieved content can install or change contracts.

Before invoking any handler, preflight selects tools for all steps and rejects known availability, permission, confirmation, literal-argument, and minimum-call-budget defects. Preconditions requiring live state and arguments requiring previous outputs remain execution-time checks. Partial execution is therefore still possible. Results include attempted write step IDs and a reconciliation flag so a caller does not assume whole-run replay is safe after a later failure.

For consequential operations, support independent state verification where the integration allows it. A timeout can mean the action completed but its response was lost; report an unknown outcome until reconciled.

## Recovery boundaries

| Failure | Intended response |
| --- | --- |
| Invalid arguments or missing required information | Correct only from available evidence; otherwise request clarification |
| Permission denied | Stop or escalate; do not route around the restriction |
| Transient failure on a read-only operation | Retry within a defined limit and backoff budget |
| Timeout on a state-changing operation | Reconcile state or use a supported idempotency key before considering a retry |
| Unavailable tool | Retrieve an authorized alternative with compatible semantics |
| Failed postcondition | Record failure; reassess without assuming replay is safe |
| Exhausted budget | Stop and return partial results with unresolved conditions |

Tools must declare their side effects accurately. Hard execution deadlines require cancellable adapters or process isolation; an in-process thread timeout alone cannot stop a running function.

## Trace design

Record run and step identifiers, selected strategy and reason, candidate tool identifiers, call count, timings, validation outcomes, failure classes, recovery attempts, and final status. Avoid raw arguments, outputs, credentials, and personal data in default traces. Record model token usage and estimated cost only when usage and pricing metadata are available; represent missing metrics as unknown.
