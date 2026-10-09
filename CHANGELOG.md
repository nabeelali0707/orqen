# Changelog

## 0.1.0a1 — initial alpha candidate

Orqen is an experimental Python execution and evaluation SDK. APIs may change.
This release does not claim improved agent reasoning or production readiness.

### Included

- Typed tool registry, dependency-aware plans, JSON Schema contracts, application
  permissions and confirmations, independent verification, and bounded read retries.
- Observation-driven application stages under shared budgets, with uncertain-write
  reconciliation metadata and no automatic write replay.
- Strict JSON planning with optional application-owned step identifiers; optional
  Ollama, Mistral and OpenRouter transports; experimental proposal/review planning.
- Checkpointed model experiments and a pinned AgentArch mock-data/grader adapter.
- Officially graded, bounded whole-plan/observation-driven AgentArch pilot runner;
  all 110 finish-only negative controls rejected, without model inference.
- Authenticated local API, execution dashboard and MCP stdio interface.
- Stateful regression fixtures, a conditional refund sandbox, and an audited wheel.

### Evidence and limits

- 266 tests passed before release preparation; CI passed on commit `9a6d08a`.
- The refund sandbox met expected behavior in 32 scenarios: 26 completions, three
  blocked stale writes and three uncertain writes requiring reconciliation.
- A constrained local Llama arithmetic attempt passed after an unconstrained
  attempt failed on output naming. The earlier Qwen run verified 0/16 tasks.
- These development fixtures and single-case diagnostics are not held-out research
  results. The AgentArch adapter has compatibility evidence, not a model benchmark.
- Hosted inference is unvalidated. The service is single-process and locally tested;
  real backend integration, operational controls and public deployment are pending.
