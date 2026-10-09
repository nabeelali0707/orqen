# Development milestones

## 0. Project foundation

- [x] Connect the local folder to the Orqen GitHub repository.
- [x] Establish the project name, five-stage architecture, and research boundaries.
- [x] Specify a controlled evaluation plan.

## 1. Executable Python SDK prototype

- [x] Package structure and typed contracts for tools, tasks, results, and traces.
- [x] ToolRegistry, transparent TaskAnalyzer, StrategyRouter, and ToolRouter.
- [x] Input/output validation and application-owned permissions.
- [x] Function execution with task postcondition checks.
- [x] Bounded recovery for safe transient failures.
- [x] Local examples and behavioral tests covering failures and side effects.
- [x] Whole-plan preflight for known defects before writes, plus partial-write reconciliation metadata.
- [x] Observation-driven application stages with shared budgets and independent final verification.
- [x] Conditional refund sandbox with ledger grading, stale-state checks and uncertain-write tests.

## 2. Controlled local experiments

- [x] Fixed ordering versus lexical ranking, crossed with read recovery on/off.
- [x] Dependent-step ordering and reference-based data flow; plans are application- or adapter-supplied.
- [x] Stateful regression fixtures, reproducible configurations, and redacted trace export.
- [x] Local fault-suite results with overhead and failure analysis.
- [ ] Independently held-out tasks and real model comparisons. Local fixtures are not held-out evidence.
- [ ] Distinct reasoning implementations before any strategy-selection comparison.
- [x] Catalog-level coverage experiment with multiple capabilities and prerequisite labels.
- [x] Full, fixed top-k, and adaptive lexical catalog policies with explicit expansion.

After the independent review, action contracts and independent grading take priority over additional agent architectures. Lexical ranking remains opt-in; no benefit has been established on the current fixtures. See `docs/research-review.md` and `docs/local-results.md`.

## 3. Research integration

- [x] Model adapter, explicit settings, model digest and server-version capture.
- [x] Provider-neutral JSON transport adapter, response validation, and planning-call budgets.
- [x] Optional Ollama HTTP transport with explicit model settings, usage records, and offline contract tests.
- [x] Mistral/OpenRouter transports, explicit credential loading, request limits and offline tests.
- [ ] Hosted provider live compatibility and model selection; credentials have not been used.
- [x] Live compatibility check: Qwen passed; Llama contract failure is retained in the evidence report.
- [x] Bounded one-call model smoke command with a network-free dry-run mode.
- [x] AgentArch data/tool/grading adapter pinned to an upstream revision; both use cases validated.
- [x] Repeated-trial runner and live local ablation run; 0/16 verified outcomes are recorded in [model results](model-results.md).
- [x] Concrete proposal/review agents with independently counted planning calls and enforced budgets.
- [x] Atomic experiment checkpoints, partial-run status and network-free schedule preview.
- [x] Explicit application step identifiers; one constrained Llama diagnostic passed the unchanged verifier.
- [x] Officially graded AgentArch attempt runner, frozen protocol metadata and all-case negative controls.

## 4. Product interfaces, subject to evidence

- [x] Self-hostable API and bearer authentication, exercised over local HTTP.
- [ ] Public deployment: hosting destination, domain/TLS and production configuration still required.
- [x] Execution dashboard with authenticated workflows, history, and verification evidence; browser-tested.
- [x] MCP stdio server using the official SDK; tested with a real MCP client.

Each major milestone should produce a reviewed diff, relevant passing checks, and a descriptive local commit. Do not push until the user explicitly authorizes it again. A milestone is not complete merely because its interfaces have been scaffolded. See [the completion plan](completion-plan.md) for remaining work and required owner inputs.

## 5. SDK distribution

- [x] Offline wheel build, runtime-asset audit and installed-wheel workflow smoke.
- [x] Wheel checks added to the Python 3.11–3.14 CI matrix.
- [ ] Updated remote CI passing on the release commit.
- [x] MIT license, alpha versioning, release notes and manual Trusted Publishing workflow.
- [ ] Owner's package registry/account configuration and first registry installation check.
- [ ] SDK publication, explicitly deferred until the release gates are met.

See [release readiness](release-readiness.md). Engineering validation does not
establish adaptive-reasoning superiority or production readiness.
