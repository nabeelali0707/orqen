# Architecture proposal

## Core boundary

The Python SDK mediates between an application, a model adapter, and registered tools. Core decisions and trace formats should remain independent of a model provider. A hosted API, dashboard, and MCP integration are later interfaces over the same engine.

The following modules describe intended behavior, not existing implementations.

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

Begin with transparent rules. A direct response uses no tools. Function calling handles a bounded tool interaction. Plan-and-execute handles dependent steps with explicit intermediate results. Multi-agent execution is a later experimental strategy for separable specialist work, with coordination cost included in evaluation.

Do not silently label sequential calls as multi-agent execution. Expose supported strategies explicitly, and report unsupported requests. Model recommendations do not grant permissions or bypass validation.

## Execution contract

Before invocation, check tool availability, schema validity, application permissions, required confirmation, and remaining call/time budgets. Validate outputs against their contracts, then evaluate task-specific postconditions. A syntactically valid response does not establish business success.

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
