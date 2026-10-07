# What remains to complete Orqen

Status: October 7, 2026. The research and interface implementations
have been prioritized. They establish a working prototype, not a validated adaptive
reasoning improvement or a deployed production service.

## Implemented and checked

- Modular SDK with permissions, contracts, whole-plan preflight, task verification,
  bounded read recovery and uncertain-write metadata.
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
| Intended release/license and deadline | A distributable SDK or scoped production pilot |

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

The API is locally tested and self-hostable. Public hosting is not deployed. The
SQLite service supports one process per database, bounded concurrency and history,
and no automatic replay of uncertain operations. Production still needs real
backend idempotency/reconciliation, retention procedures, TLS, token lifecycle
management, monitoring and workload-specific review. The Dockerfile is a deployment
artifact, not evidence that a container was deployed.

## Git policy

Commit verified milestones locally. Do not push until explicitly authorized again.
