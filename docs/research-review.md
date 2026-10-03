# Independent project review

Reviewed October 3, 2026. Evidence, hypotheses, and engineering decisions are distinguished below. This review supersedes the assumption that every box in the original diagram needs a separate intelligent subsystem.

## 1. Actual problem and corrections

The useful problem is completing a business workflow correctly under uncertainty, with bounded cost and acceptable side effects. Tool selection is one contributor. Other contributors include missing business rules, stale state, ambiguous objectives, authorization, data dependencies, observation quality, and incomplete execution.

Three original assumptions need correction:

- Different architectures winning on different tasks does not establish that a practical router can predict the winner cheaply enough to help.
- A smaller tool shortlist is not inherently better. Missing a prerequisite can make the entire task impossible.
- Schema-valid arguments and a successful response do not establish an authorized action or correct state transition. A final verifier cannot undo an incorrect write.

## 2. Primary-source review

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| [AgentArch v2](https://arxiv.org/html/2509.10769v2) | Architectural preferences vary; evaluation combines tool choice, arguments, and outcome. The study covers two workflows with 60 samples each and does not measure efficiency. | A universal architecture, causal superiority of an adaptive router, or general enterprise reliability. |
| [AgentArch tool registry source](https://github.com/ServiceNow/AgentArch/blob/main/agent_arch/tools/tool_registry.py) | Generated tool functions return mocked responses indexed by record identifier and tool name. | Real database commits, rollback, idempotency, or transaction recovery. |
| [AgentArch grading source](https://github.com/ServiceNow/AgentArch/blob/main/agent_arch/metrics.py) | Grades calls against ground truth; final outcome matching uses expected text within the final message. | Independent verification that a production backend changed correctly. We should retain its official grader for comparable runs and add separate stateful tests. |
| [Select-then-Solve](https://arxiv.org/abs/2604.06753) | Authors report a learned router outperforming a best fixed paradigm on their evaluations; self-routing is not consistently effective. | Transfer of those results to Orqen or enterprise tool workflows without training and testing. |
| [How Many Tools Should an LLM Agent See?](https://arxiv.org/abs/2605.24660) | Investigates coverage versus shortlist size and a chance-corrected metric. Its RL policy is described as a probe of the metric. | A turnkey production router or proof adaptive depth always wins. |
| [AutoTool](https://arxiv.org/abs/2511.14650) | Studies graph-based reuse of historical tool trajectories to reduce inference. Submitted November 2025; accepted at AAAI 2026. | Safe transfer across changed state, permissions, or tool versions. Orqen has no trajectory corpus yet. |
| [Pydantic AI tools](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/) | Already supports argument validators, retry semantics, approval, and tool timeouts. | Application-specific policies or guaranteed correctness from default configuration. |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Provides checkpoints and stores for memory, interruption recovery, and fault tolerance. | A reason for Orqen to build another persistence framework before proving value. |
| [Anthropic tool search](https://www.anthropic.com/engineering/advanced-tool-use) | Provider-level deferred tool discovery already exists, with context savings and added search overhead described. | Vendor-independent superiority of an additional Orqen retrieval layer. |

Citation detail: the AgentArch abstract landing page uses *A Comprehensive Benchmark to Evaluate Agent Architectures in Enterprise*, while v2 HTML uses *A Benchmark for Evaluating Agent Architectures in Enterprise Workflows*. Use the arXiv identifier and version to avoid ambiguity.

## 3. Opportunity and overlap

There is no defensible novelty claim in combining a registry, schemas, retries, and agent routing. These are established features. A credible, still unproven opportunity is a small, provider-independent way to specify action contracts, compare policies under the same stateful grader, and explain when recovery is unsafe.

The difficult work is domain integration: obtaining trustworthy preconditions and postconditions, maintaining adapters, and validating results independently of the model. A configurable wrapper is useful only if developers can add these contracts with less effort than using their existing framework directly. Novel research and product demand remain unproven.

## 4. Component decisions

| Original component | Decision | How to justify keeping it |
| --- | --- | --- |
| Task Analyzer | Keep as cheap plan metadata; defer a separate LLM classifier | Measure useful predictive power before adding an inference call |
| Strategy Router | Keep compatibility labels; stop treating them as distinct implemented reasoning algorithms | Implement distinct solvers before running strategy superiority experiments |
| Registry + Tool Router | Keep simple capability contracts and lexical ranking; no embeddings yet | Measure recall, selection, exposure, and end-to-end success against full catalog and fixed top-k |
| Schema + Permission + Execution | Keep in one execution boundary; reuse jsonschema | Prevent invalid and unauthorized invocations in fault tests |
| Verification | Strengthen with pre-call and per-step application checks | Prevent unsafe writes and block dependent actions after bad observations |
| Recovery | Keep conservative read retries; defer autonomous argument repair and write replay | Count recovered tasks, extra calls, and duplicate effects |
| Evaluation | Implement now with independent graders | Expose improvements, regressions, and unmeasured quantities |
| Multi-agent, hosted API, dashboard, MCP server | Defer | Require a measured need that cannot be met by a small integration |

## 5. Alternatives

1. Ordinary application code and a fixed workflow: strongest default when business steps are known. Predictable and easy to audit; less flexible for open-ended tasks.
2. Existing agent framework plus application validators: preferred production path when framework features are needed. Orqen should eventually integrate at that boundary instead of duplicating its runtime.
3. Retrieval-only middleware: smaller experiment for a large tool catalog; useful only if retrieval is the bottleneck.
4. Learned strategy selection: plausible research track, but requires distinct solvers, training labels, held-out tasks, and cost-aware evaluation.

## 6. Recommended design

Retain Python because the working prototype, async tools, and test harness already fit a local SDK. Avoid a service until multiple-language access, centralized governance, or deployment needs justify it. No framework migration is needed for this experiment.

Use three logical parts: a planner adapter proposes a plan; a contract-enforcing executor selects and invokes tools; an independent evaluator grades state and traces. The existing small modules can remain source files, without treating each as an autonomous agent. No model-generated plan can create permissions or validators.

Add tool preconditions before every attempt and postconditions before releasing outputs to dependent steps. Treat omitted side-effect metadata conservatively. Application checks are not transactions: concurrent state changes still require atomic authorization and conditional updates in the backend.

## 7. Experiments that can falsify the idea

First run deterministic fault scenarios to establish executor behavior. Cross lexical ranking on/off with safe recovery on/off, retaining access checks and contracts in every configuration. These are regression fixtures, not held-out research tasks. Strategy labels alone must not become an experimental treatment.

Then compare a plain fixed workflow, an existing framework with the same contracts, and Orqen on a genuinely held-out task set. Freeze model/version, prompts, tools, permissions, state seeds, budget, and grader. Include ambiguous requests, irrelevant tools, schema-valid wrong identifiers, partial writes, lost responses, policy changes, and no-fault cases. Separate task completion from safe refusal and unverified outcomes.

For retrieval research, expose full catalog, fixed top-k, and adaptive retrieval to the same real planner, with a separate required-tool oracle. Measure prerequisite coverage, argument correctness, successful state transitions, token usage, total latency, and cost per successful task. Do not interpret our current capability filter as a full-catalog model experiment.

Use paired repeated trials across independent tasks; report per-task failures and uncertainty. Predeclare acceptable trade-offs with the deployment context. Reject adaptive features if a simpler system matches success with lower overhead, or if improvements vanish on held-out tasks. Stop claiming a product advantage if framework integration is simpler and equivalent.

## 8. Smallest useful implementation

Preserve the tested async executor. Add before/after action contracts, conservative side-effect defaults, stateful fault fixtures, a reproducible evaluation CLI, and metadata-only trace export. Document current planner limitations. Defer model spending and benchmark execution until a configured provider, budget, and suitable held-out tasks exist.

## 9. Execution and limitations

The initial SDK passed 48 local tests before this review. Its direct/function/plan labels share one sequential executor, and its planner sees the full authorized catalog. Therefore the initial code does not demonstrate adaptive reasoning or reduced model context. The example is a supplied plan, not a natural-language agent.

Follow-up implementation added the action contracts and evaluation described above; see [local results](local-results.md). It does not provide durable resume, atomic authorization, exactly-once effects, automatic compensation, live policy learning, or general semantic correctness. Cooperative async timeouts cannot forcibly stop blocking Python code.

## 10. Honest assessment

The problem is real; the original breadth is premature. Existing work supports investigating task-dependent policies but does not establish that this project needs all proposed components. The strongest immediate result is a testable execution boundary and a way to disprove inflated claims. Commercial usefulness, research novelty, and superiority over existing frameworks still require evidence from real integrations and controlled model experiments.
