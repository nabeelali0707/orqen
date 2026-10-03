# Orqen development instructions

- The project name and intended Python package name are `orqen`.
- Follow the five-stage architecture in `docs/architecture.md`.
- Start with a modular Python SDK; keep provider adapters separate from core policy.
- Commit after each major completed milestone, after relevant checks pass, then push when authorized by the active task.
- Keep research hypotheses separate from measured results. Never describe local fixtures as AgentArch benchmark results.
- Enforce permissions independently of model decisions. Bound recovery and avoid replaying uncertain state-changing operations.
- Do not put secrets or raw execution data in source control.
