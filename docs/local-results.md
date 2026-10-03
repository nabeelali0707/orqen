# Local fault-suite results

Run date: October 4, 2026 (Asia/Karachi). These are deterministic development fixtures, not held-out research, LLM, or AgentArch results.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m orqen.cli evaluate --repetitions 5 --seed 17 --output runs/local-evaluation.json --traces runs/local-traces.jsonl
```

Environment: Windows, Python 3.14.3, Orqen 0.1.0, jsonschema 4.26.0. Source fingerprint: `c769e090eff58f38fa82ad5ca59ce48704dffeca45d9a54f316f0f5992f9c5c8`.

The run contains 180 attempts: nine cases, four configurations, five repetitions. Each configuration has 20 completion attempts and 25 fault-handling attempts. State resets between attempts; the schedule is shuffled with seed 17. Every mode enforces the same contracts, permissions, and budgets.

## Observations

| Configuration | Completion successes | Expected behavior, all cases | Calls | Retries | Median ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| Fixed order, no recovery | 15/20 | 40/45 | 35 | 0 | 0.473 | 0.738 |
| Ranking only | 15/20 | 40/45 | 35 | 0 | 0.504 | 0.824 |
| Recovery only | 20/20 | 45/45 | 40 | 5 | 0.512 | 13.164 |
| Ranking and recovery | 20/20 | 45/45 | 40 | 5 | 0.517 | 4.189 |

All configurations recorded zero policy violations and zero false success reports under the fixture graders. Each configuration returned ten unknown outcomes: five committed writes with lost acknowledgements and five false acknowledgements rejected by independent postconditions. No write was retried.

Recovery converted the five injected transient-read failures into completions, using five extra calls per recovery-enabled configuration. That confirms the configured retry behavior. It does not demonstrate better agent reasoning. Tail latency increases because retry delay and Windows scheduling count in the measurement; these tiny samples do not establish a comparative speed claim.

Ranking changed no outcomes. Each step in this suite has only one matching capability, so the experiment does **not** meaningfully test ranking quality. The unrelated tools are excluded deterministically before execution. Claiming that their presence tests LLM distraction or proves adaptive retrieval would be incorrect.

## Decisions

- Keep bounded recovery for explicitly read-only transient failures.
- Keep preconditions and step-level postconditions to prevent unsafe continuation in these fault cases.
- Preserve fixed tool order by default; lexical ranking remains an opt-in experiment without demonstrated selection benefit.
- Do not evaluate strategy labels as different reasoning methods: they currently share the same executor.
- Do not report monetary cost, token savings, or model tool-selection accuracy. They were not measured.

The next useful research experiment needs multiple genuinely plausible tools, independent prerequisite labels, a real planner, and held-out stateful tasks. It must compare against plain workflow code and an existing framework using equivalent contracts. A useful product advantage remains unproven.

Raw report and JSONL traces are stored locally under the Git-ignored `runs/` directory. The CLI regenerates them; this document records the observed aggregate results only.

## Implementation validation

A fresh isolated environment at `.venv/isolated` installed the package successfully. All 73 tests passed there, Ruff lint and formatting checks passed, and `pip check` reported no broken requirements. This isolates Orqen from unrelated protobuf conflicts in the machine's shared Python packages; those global packages were not changed. Local validation used Python 3.14.3. CI also defines Python 3.11–3.14 jobs.
