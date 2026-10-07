# Model experiments and proposal/review agents

`orqen evaluate-model --model llama3.2:3b --repetitions 2 --output runs/model-evaluation.json`
runs full-catalog planning, lexical retrieval, recovery disabled, and proposal/review
planning on normal and transient-failure arithmetic cases. Each attempt creates fresh
tool state and transport records. Trial seeds are paired across variants; execution
order is shuffled with the recorded order seed. Reports contain model digest, Ollama
version, explicit sampling settings, source fingerprint, token usage and verified outcomes.
The model identity is checked before and after the experiment. A changed identity
invalidates a comparison. Seeds/settings aid reproducibility but cannot guarantee
bitwise deterministic inference across hardware and server versions.

For a smaller diagnostic schedule, preview before running:

```sh
orqen evaluate-model --model qwen2.5-coder:7b --repetitions 1 --variants baseline proposal_review --faults none --dry-run
```

The preview makes no network requests. Remove `--dry-run` to execute the selected
local model schedule. `--faults` accepts `none`, `transient`, or `both`; selection
does not change the original grader. CLI runs checkpoint metadata atomically before
the first attempt and after every completed attempt. SDK callers can pass
`checkpoint=Path(...)` to `evaluate_models` for the same behavior.

An interrupted checkpoint has `report_status: running`; do not treat its partial
denominator as the complete schedule. If the final identity query fails, completed
rows remain available with `report_status: identity_unavailable` and
`identity_stable: null`. The CLI exits nonzero when either source or model identity
stability is not established. There is no automatic resume or replay of trials.

The proposal/review implementation makes two independent planner calls. The reviewer
receives the original goal and proposed plan, then returns a complete replacement plan.
Both calls count against the engine planning budget; insufficient budget prevents the
proposal from starting. Catalog expansion can require another pair of calls. Errors
stop the pair without executing any tool. The central executor enforces the same
permissions, confirmation rules, schemas and verification for both architectures.
An explicit multi-agent label without this planner remains unsupported.

This is a small synthetic integration experiment. Recovery is tested by an injected
read failure, and retrieval by a two-tool catalog. These cases do not establish
enterprise performance, general reasoning gains or AgentArch results. The architecture
is opt-in; its extra latency and tokens require justification on held-out tasks.
