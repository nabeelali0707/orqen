# Local model evidence recorded October 4, 2026

Reviewed October 5, 2026. These are synthetic smoke and arithmetic experiments,
not AgentArch benchmark scores. Raw reports remain under ignored `runs/`.

## Compatibility smoke

Qwen `qwen2.5-coder:7b` passed the addition smoke: one planning request, one tool
call, and an independently verified `sum` result. The request took approximately
162 seconds including startup/processing. Llama `llama3.2:3b` initially timed out,
then produced an invalid plan. After provider grammar specialization, its tool
call executed but failed the required output-step contract. Those failures remain
in the local reports; a successful request alone does not establish task success.

## Repeated ablations

Command: `orqen evaluate-model --model qwen2.5-coder:7b --repetitions 2 --timeout 180`.
Each variant has two trials with and without an injected transient read failure.
The task requires an `add` call with operands 7 and 4 and output step `sum`.

| Variant | Verified / attempts | Planning calls | Tool calls | Mean elapsed seconds |
| --- | --- | --- | --- | --- |
| Full catalog baseline | 0 / 4 | 4 | 6 | 60.88 |
| Lexical retrieval | 0 / 4 | 4 | 6 | 52.28 |
| Recovery disabled | 0 / 4 | 4 | 4 | 62.18 |
| Proposal/review agents | 0 / 4 | 8 | 0 | 128.46 |

There were 14 final verification failures and two transient errors in the
recovery-disabled variant. The proposal/review plans made no tool calls, so they
could not satisfy the task's required-tool condition. The metadata reports omit
raw plans and outputs, which limits diagnosis of the remaining verification
failures. Do not infer exact wrong arguments or outputs from these traces.

Sampling used temperature 0, paired seeds 0 and 1, a 512-token output limit,
8192 context tokens and a 180-second per-request timeout. Order seed was 0.
Ollama version was `0.30.10`; model quantization was `Q4_K_M`. The recorded model
digest was stable before and after the run:
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
The report's source fingerprint was
`f3956585faeb7cd5907494871e5b82183a21eb4c7ff1a025993d226ad75ab19d`.
This fingerprint was taken at report creation, not from a frozen release checkout;
unrelated interface development occurred while the experiment ran. A publication
run must use an immutable checkout and record its identity before execution.

These small, repeatedly used tasks do not support a statistical comparison or an
enterprise generalization. Temperature-zero repetitions do not establish independent
reasoning samples. The observed added review cost came with no verified successes.
The next experiment should first diagnose the contract failures with a deliberately
scoped synthetic debugging trace, then freeze an evaluation set and code revision.

Mistral and OpenRouter adapters were tested offline on October 5. No hosted API
inference or hosted task-success measurement has been performed.

### Offline diagnosis and next-run instrumentation (October 5)

Inspection of the existing call-event metadata found `sum_step` identifiers in
the single-planner variants, where the fixture requires `sum`. This establishes
a naming-contract failure, but does not establish that the arithmetic or operands
were correct. The proposal/review variant made no tool calls.

The shared planning instructions now emphasize exact requested identifiers and
that proposed tools have not executed. The reviewer receives the same explicit
warning. These are candidate prompt fixes, not measured improvements.

Future reports separate required-tool, operand, output-name, and value checks as
booleans without recording raw outputs. The original pass criterion is unchanged.
The runner accepts selected variants and fault conditions for smaller diagnostic
experiments, and records source fingerprints before and after execution. Matching
fingerprints detect no endpoint difference; they cannot prove that code was never
changed and restored during a run. An immutable checkout remains necessary for
publication. Mock-transport tests verify the diagnostics and grading behavior;
no new model inference was used for this milestone.

### October 7 operational attempt

A two-attempt Qwen diagnostic schedule (baseline and proposal/review, no injected
fault, one trial, 240-second request limit) was started from package source at
commit `1c8e403`. Local prompt processing was slow and coincided with substantial
slowdown of other validation processes. The validation-owned Ollama process was
stopped. The runner then failed its final identity query before saving the report.
No trustworthy per-trial outcome report survived, so this attempt contributes no
success-rate measurement and does not validate the prompt changes.

This exposed a reporting defect: completed rows were lost when the final identity
check raised. The runner now checkpoints each completed attempt and preserves rows
with unknown identity stability when that final query fails. Offline tests cover
server disappearance, cancellation and failed atomic report replacement. These
fixes cannot reconstruct the missing outcomes from the earlier attempt.

### October 7 Llama diagnostic

One baseline attempt using installed `llama3.2:3b` completed from commit `1dba805`.
It made one planning call and one tool call in 72.00 seconds. The independent
diagnostics confirmed the required tool, operands 7 and 4, and value 11. The exact
output identifier was wrong, so the unchanged verifier failed: **0/1 verified**.
This directly shows that a prompt reminder alone did not fix this case.

Model and source fingerprints were stable across the run. Ollama was `0.30.10`,
model digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`,
Q4_K_M, temperature 0, seed 0, 512 output tokens, 8192 context tokens and a
180-second request timeout. Usage was 773 input tokens and 51 output tokens.
Source SHA-256 was
`f026c3ec48a6dcf8598caad1bf19adbccf03d008fae4e2f15c16f3400de9f010`.

This motivates an explicit, optional application-owned identifier contract in
`JSONPlanner`. It supplies the same requested names as structured constraints,
without renaming generated output or changing the original task grader. The model
evaluation runner records this as a distinct `constrain_step_ids` treatment; the
default remains unconstrained for reproducibility of the earlier configuration.

### October 7 constrained identifier check

One baseline attempt from commit `1799d76`, with `constrain_step_ids=true`, passed
the unchanged verifier: **1/1 verified**. All four diagnostics passed: required
tool, operands, identifier and arithmetic value. It used one planning call and one
tool call, taking 54.59 seconds, with 729 input tokens and 50 output tokens.
Model digest, server version, seed, temperature, token/context limits and timeout
matched the preceding Llama diagnostic. Model and source fingerprints were stable;
source SHA-256 was
`4330c3937571a961599ebf9ccc49dce2877020b289699e212f76b2a56ad3e273`.

The explicit schema constraint fixes this observed contract case without rewriting
the response or relaxing the verifier. These sequential one-case diagnostics are
not independent held-out evaluation, a statistical comparison, a latency advantage
or evidence of improved reasoning. The old unconstrained failure remains part of
the record. No hosted inference or AgentArch model benchmark was performed.
