# Evaluation plan

## Research question

Does task-dependent strategy selection combined with adaptive tool retrieval, validation, verification, and bounded recovery improve end-to-end task success at acceptable latency and cost compared with a fixed architecture?

This is a hypothesis. Unit tests and synthetic demonstrations cannot establish an improvement on AgentArch.

## Comparisons

1. Fixed strategy with the full permitted tool set.
2. Same strategy with adaptive tool retrieval only.
3. Adaptive strategy selection with the full permitted tool set.
4. Full adaptive system with verification and bounded recovery.

Keep mandatory permission enforcement and basic input safety in every configuration. Add ablations for verification and recovery to separate their contributions without weakening access control.

Fix the model and version, tasks, tool implementations, permissions, information available, sampling settings, call/time budgets, and evaluation criteria across comparable runs. Record configuration differences explicitly. Separate development tasks from held-out evaluation tasks so routing rules do not encode test answers.

## Workloads

Start with deterministic local fixtures: a direct-response task, a single tool call, dependent reads, a transient read failure, invalid arguments, denied access, an ambiguous write timeout, and a failed business postcondition. Add irrelevant tools to measure retrieval coverage and selection behavior.

Then build an AgentArch adapter following the official benchmark setup and evaluation rules. Preserve task definitions and graders; record the upstream revision and any deviations. The adapter and benchmark runs are future work.

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
- Additional related-work claims in the supplied brainstorming notes require primary-source verification before being included as evidence.
- No experiments have been run for Orqen. No baseline or improvement numbers are available.
