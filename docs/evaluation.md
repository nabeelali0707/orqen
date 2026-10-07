# Evaluation plan

## Research question

Does task-dependent strategy selection combined with adaptive tool retrieval, validation, verification, and bounded recovery improve end-to-end task success at acceptable latency and cost compared with a fixed architecture?

This is a hypothesis. Unit tests and synthetic demonstrations cannot establish an improvement on AgentArch. The [independent review](research-review.md) narrows the immediate implementation to action contracts and stateful evaluation.

## Run the implemented local suite

```powershell
.\.venv\Scripts\python.exe -m orqen.cli evaluate --repetitions 5 --seed 17 --output runs/local-evaluation.json --traces runs/local-traces.jsonl
```

Nine deterministic scenarios run under four configurations: fixed tool ordering, lexical ranking only, safe read recovery only, and ranking plus recovery. All use the same sequential executor, contracts, permissions, and budgets. The schedule is shuffled with a recorded seed, and scenario state is recreated for every attempt. A source hash and environment versions accompany each report.

The four completion cases are direct response, single read, dependent reads, and transient read. The five fault cases are a denied write, business-limit violation, wrong-record observation, lost write acknowledgement, and false write acknowledgement.

Completion success is graded against expected outputs for completion cases only. Expected-behavior rate additionally checks required failure categories and state for fault cases. Policy violations inspect the fixture ledger. False success means the executor claims verification while the independent grader rejects the goal. A committed write with a lost acknowledgement has a satisfied state goal but correctly remains `unknown` to the executor.

This suite does not test model tool selection, natural-language planning, held-out generalization, or adaptive reasoning. Irrelevant tools cannot confuse this deterministic capability filter. Repeating the fixtures checks reset behavior and timing; it does not create additional independent research tasks. See [measured local results](local-results.md).

## Comparisons

The separate [catalog coverage experiment](catalog-results.md) now compares the full catalog, fixed top-1/top-3, and an adaptive lexical cutoff on prerequisite-labeled queries. Run `orqen evaluate-catalog` for that report. This measures retrieval coverage, not the future model-based comparisons below.

1. Fixed strategy with the full permitted tool set.
2. Same strategy with adaptive tool retrieval only.
3. Adaptive strategy selection with the full permitted tool set.
4. Full adaptive system with verification and bounded recovery.

Keep mandatory permission enforcement and basic input safety in every configuration. Add ablations for verification and recovery to separate their contributions without weakening access control.

Fix the model and version, tasks, tool implementations, permissions, information available, sampling settings, call/time budgets, and evaluation criteria across comparable runs. Record configuration differences explicitly. Separate development tasks from held-out evaluation tasks so routing rules do not encode test answers.

## Workloads

Start with deterministic local fixtures: a direct-response task, a single tool call, dependent reads, a transient read failure, invalid arguments, denied access, an ambiguous write timeout, and a failed business postcondition. Add irrelevant tools to measure retrieval coverage and selection behavior.

The pinned AgentArch adapter is implemented and compatibility-tested. Benchmark
runs remain pending. Preserve task definitions and official graders; record the
upstream revision and any deviations. See `agentarch.md`.

## Metrics

| Metric | Operational definition |
| --- | --- |
| Task success | Fraction of all attempted tasks satisfying the independent task grader |
| Retrieval coverage | Fraction of required tools included in retrieved candidate sets, where labels exist |
| Tool-selection accuracy | Fraction of selected calls judged appropriate for the current step |
| Argument validity | Fraction of proposed calls passing schema and task constraint checks before correction |
| Unnecessary calls | Calls labeled noncontributing by a specified rubric |
| Latency | Total elapsed time including analysis, routing, verification, and recovery; report median and tail latency |
| Cost | Recorded model/infrastructure cost per attempt and per successful task; unknown when unavailable |
| Recovery effectiveness | Fraction of eligible failed tasks converted to independently verified successes |
| Safety violations | Unauthorized actions, duplicate side effects, and false success reports |

Use repeated trials for stochastic models. Publish trial counts, failure categories, task-category breakdowns, and uncertainty intervals. Define any pass@1 or repeated-success metric precisely before reporting it. Report latency and cost even when success improves.

## Evidence status

- Verified source: [AgentArch paper](https://arxiv.org/abs/2509.10769) and [official code](https://github.com/ServiceNow/AgentArch).
- Relevant related-work sources were verified in the [independent review](research-review.md); their results do not transfer automatically to Orqen.
- The local fault and conditional-workflow suites establish fixture behavior only.
- A local Qwen arithmetic ablation run verified 0/16 tasks; see `model-results.md`.
  No AgentArch model benchmark or held-out enterprise comparison has run.
