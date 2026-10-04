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
