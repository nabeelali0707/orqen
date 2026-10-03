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

- [ ] Model adapter and reproducible model settings.
- [x] Provider-neutral JSON transport adapter, response validation, and planning-call budgets.
- [ ] Live provider transport with recorded model settings and usage; no live model tested yet.
- [ ] AgentArch adapter with documented upstream revision.
- [ ] Repeated trials and component ablations.
- [ ] Multi-agent strategy only as an explicit, measurable implementation.

## 4. Product interfaces, subject to evidence

- [ ] Hosted API and authentication.
- [ ] Execution dashboard.
- [ ] MCP compatibility.

Each major milestone should produce a reviewed diff, relevant passing checks, and a descriptive commit before pushing. A milestone is not complete merely because its interfaces have been scaffolded.
