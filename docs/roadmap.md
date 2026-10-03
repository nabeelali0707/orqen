# Development milestones

## 0. Project foundation

- [x] Connect the local folder to the Orqen GitHub repository.
- [x] Establish the project name, five-stage architecture, and research boundaries.
- [x] Specify a controlled evaluation plan.

## 1. Executable Python SDK prototype

- [ ] Package structure and typed contracts for tools, tasks, results, and traces.
- [ ] ToolRegistry, transparent TaskAnalyzer, StrategyRouter, and ToolRouter.
- [ ] Input/output validation and application-owned permissions.
- [ ] Function execution with task postcondition checks.
- [ ] Bounded recovery for safe transient failures.
- [ ] Local examples and behavioral tests covering failures and side effects.

## 2. Controlled local experiments

- [ ] Fixed baseline and separate tool/strategy routing configurations.
- [ ] Dependent-step planning and data flow.
- [ ] Held-out task fixtures, reproducible configurations, and trace export.
- [ ] Measured results with overhead and failure analysis.

## 3. Research integration

- [ ] Model adapter and reproducible model settings.
- [ ] AgentArch adapter with documented upstream revision.
- [ ] Repeated trials and component ablations.
- [ ] Multi-agent strategy only as an explicit, measurable implementation.

## 4. Product interfaces, subject to evidence

- [ ] Hosted API and authentication.
- [ ] Execution dashboard.
- [ ] MCP compatibility.

Each major milestone should produce a reviewed diff, relevant passing checks, and a descriptive commit before pushing. A milestone is not complete merely because its interfaces have been scaffolded.
