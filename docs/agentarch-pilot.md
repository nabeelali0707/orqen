# Officially graded AgentArch pilot

`scripts/benchmark_agentarch.py` connects Orqen execution to the pinned official
AgentArch grader. It previews without inference by default. Reports contain scalar
metrics, usage, budget and provenance metadata; prompts, labels, generated answers,
arguments and tool observations are not persisted. Keep reports under ignored `runs/`.

The official grader imports pandas, NumPy, PyYAML and Pydantic through upstream
utilities. Use an environment with those dependencies installed and record the
versions; the script records them automatically. On Windows use `python -X utf8`.
No dependencies or model weights are downloaded by this script.

```sh
# Preview two modes on case 2; zero inference requests.
python -X utf8 scripts/benchmark_agentarch.py --checkout runs/upstream/AgentArch --use-case requesting_time_off --cases 2

# Test the grader against a deliberately empty answer, without a model.
python -X utf8 scripts/benchmark_agentarch.py --checkout runs/upstream/AgentArch --use-case requesting_time_off --cases all --modes whole_plan --negative-control

# Explicit local-model inference; never uses hosted providers.
python -X utf8 scripts/benchmark_agentarch.py --checkout runs/upstream/AgentArch --use-case requesting_time_off --cases 2 --model llama3.2:3b --run-local
```

## Protocol and interpretation

The two modes share full permitted catalogs, independent grading and the same
tool/step/planning/time caps. `whole_plan` proposes a complete plan once; `observed`
proposes one step per planning call and receives validated observations before its
next decision. The observed mode naturally uses more planning calls; do not claim
equal realized cost. Both must use `finish` for the final answer, as expected by
the official single-agent grader. A finish step cannot precede other calls.

The script records a configuration hash before attempts, shuffles a paired schedule
using an explicit seed, resets sessions for every attempt, and checkpoints after
each attempt. Source, runner, grader and local model identities are checked at run
boundaries. A changed or unavailable identity invalidates a comparison. Interruptions
leave partial denominators rather than automatically replaying work.

Official strict success follows the pinned grader's single-agent
`overall_acceptable` predicate: correct final outcome and tool order, no hallucinated
tool, and fully correct evaluated arguments. Raw official metrics include answers
and labels, so only an explicit scalar subset is exported. A grader error is missing
evidence, not a scored success or an ordinary task failure.

These are public benchmark cases, not private held-out data. Case 1 was previously
used for compatibility development. The first local pilot uses case 2, selected
before inspecting its labels. Neither a small pilot nor the negative control can
establish architecture superiority or general enterprise reliability. All tools
remain upstream record-indexed mocks; there are no real backend writes.

The local protocol is an Orqen single-agent adaptation, not reproduction of every
AgentArch paper architecture. We preserve the official data and grader and report
our own budgets, prompt interface and runtime dependency versions as deviations.
