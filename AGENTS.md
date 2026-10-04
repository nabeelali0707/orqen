# Orqen development instructions

- The project name and intended Python package name are `orqen`.
- Treat the architecture as a hypothesis, not a constraint. Challenge it using evidence and simplify when justified; record major decisions in `docs/research-review.md`.
- Start with a modular Python SDK; keep provider adapters separate from core policy.
- Commit after each major completed milestone, after relevant checks pass. Current user instruction: keep commits local and do not push until explicitly authorized again.
- Keep research hypotheses separate from measured results. Never describe local fixtures as AgentArch benchmark results.
- Enforce permissions independently of model decisions. Bound recovery and avoid replaying uncertain state-changing operations.
- Do not put secrets or raw execution data in source control.
- Prefer the smallest useful experiment over adding framework features. Never treat strategy labels, fixture results, or schema validity as evidence of improved agent reasoning or business correctness.
