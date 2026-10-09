# What remains to complete Orqen

Status: October 9, 2026. The research and interface implementations
have been prioritized. They establish a working prototype, not a validated adaptive
reasoning improvement or a deployed production service.

## Implemented and checked

- Modular SDK with permissions, contracts, whole-plan preflight, task verification,
  bounded read recovery and uncertain-write metadata.
- Bounded observation-driven workflow stages and a conditional refund sandbox
  with independent state grading across 32 normal/fault scenarios.
- Ollama transport with explicit settings and typed provider grammar; a live Qwen
  smoke test passed. Llama's failed output-step contract is retained as evidence.
- Paired repeated-trial runner with retrieval, recovery and two-agent proposal/review
  ablations, model identity capture and metadata-only reports.
- Mistral and OpenRouter transports with safe credential loading and offline checks;
  live hosted requests remain disabled by default and have not been tested.
- Pinned AgentArch data/tool adapter for both workflows and a bridge to its official
  grader. This is compatibility evidence, not a completed benchmark.
- Authenticated HTTP API, durable metadata history and request deduplication;
  a browser-tested execution dashboard; MCP stdio tested with an actual SDK client.
  The default registered workflow is verified integer addition.

## Inputs needed from the owner

| Input | What it enables |
| --- | --- |
| First real workflow, tools/sandbox, policy rules and anonymized examples with expected outcomes | Application-specific adapters, verifiers and held-out evaluation |
| Acceptable failure, latency and cost limits; actions needing human confirmation | Meaningful acceptance criteria and execution policy |
| Hosting destination and domain, if a public service is wanted | TLS, secrets, persistent storage, monitoring and deployment |
| PyPI/TestPyPI account configuration | First publication of the prepared MIT-licensed alpha SDK |

No new model key is needed for local experiments: installed Ollama models are
available. Use local environment configuration for future provider credentials;
do not put them in tracked files.

## Remaining research and production work

The executor executes a complete proposed plan per stage. `WorkflowRunner` now
supports application-owned selection of subsequent tasks from verified observations,
with shared budgets and independent final verification. The conditional returns
sandbox validates this mechanism under synthetic faults. Model-directed replanning
and performance on real observation-dependent enterprise tasks remain unvalidated.

Freeze independent tasks and compare equivalent fixed workflows, single-agent
planning and experimental policies using the same tools, permissions and budgets.
Report business correctness, unsafe effects, uncertainty, latency and token usage.
Synthetic arithmetic/fault fixtures and adapter checks cannot establish whether
adaptive routing improves enterprise outcomes.
The local Qwen ablation run verified 0 of 16 attempts; see `model-results.md`.
Diagnose these failures before expanding comparisons. Hosted model selection and
authorized live compatibility checks are still pending.

October 7 diagnosis found correct Llama arithmetic but an incorrect internal output
name. An explicit optional step-ID contract then passed one constrained diagnostic
without changing the grader. Atomic checkpoints now preserve completed attempts if
the final model identity query fails. These are integration fixes, not held-out
reliability evidence. The SDK wheel is locally checked; publication gates are listed
in `release-readiness.md`.

Alpha release preparation now includes `0.1.0a1` metadata, MIT licensing, release
notes, a manual Trusted Publishing workflow, tag/artifact checks, and package smoke
validation. The AgentArch runner now invokes the official grader after bounded
whole-plan or observation-driven attempts. It rejected all 110 empty-answer negative
controls. A local model pilot was blocked by execution approval review before
inference and is not counted as a benchmark result. See `publishing.md` and
`agentarch-results.md` for the concrete remaining external steps and evidence.

The API is locally tested and self-hostable. Public hosting is not deployed. The
SQLite service supports one process per database, bounded concurrency and history,
and no automatic replay of uncertain operations. Production still needs real
backend idempotency/reconciliation, retention procedures, TLS, token lifecycle
management, monitoring and workload-specific review. The Dockerfile is a deployment
artifact, not evidence that a container was deployed.

## Git policy

Commit verified milestones locally. Do not push until explicitly authorized again.
