# AgentArch evaluation evidence

## October 9, 2026: official-grader negative controls

The new runner executed a deliberately empty `finish` response on every case in
both pinned datasets. This is a grader rejection control, not a model benchmark
or a solver baseline. No model or external service was called.

| Use case | Attempted | Officially graded | Strict successes |
| --- | ---: | ---: | ---: |
| Requesting time off | 60 | 60 | 0 |
| Customer request routing | 50 | 50 | 0 |

All 110 attempts reached the official grader; all were correctly rejected by the
strict success predicate. Source, runner and upstream grader fingerprints remained
stable in both runs. This establishes that empty final answers do not become false
successes through the new evaluation wrapper. It does not establish model reliability.

Upstream revision: `dfdd9cd69642f74d7f2c72738c96faff7b70e59f`.
Grading dependencies were pandas 3.0.1, NumPy 2.4.3, Pydantic 2.13.4 and PyYAML
6.0.3. These differ from some upstream pinned runtime dependencies; the exact
environment is recorded in each local report. Installed Orqen distribution metadata
still read 0.1.0 during these development runs; source fingerprints identify the
working implementation. Do not describe these runs as a released artifact benchmark.

Raw local reports are ignored by Git. See `agentarch-pilot.md` for reproduction,
protocol choices, independent grading and evidence limits.
