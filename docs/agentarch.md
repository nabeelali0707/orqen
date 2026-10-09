# AgentArch adapter

The adapter targets [ServiceNow/AgentArch](https://github.com/ServiceNow/AgentArch/tree/dfdd9cd69642f74d7f2c72738c96faff7b70e59f),
revision `dfdd9cd69642f74d7f2c72738c96faff7b70e59f` (Apache-2.0).
Upstream source and data are not vendored. Clone into ignored `runs/upstream/AgentArch`
and checkout that revision. Install `orqen[research]` to load its YAML.

```python
from pathlib import Path
from orqen.agentarch import AgentArchDataset

dataset = AgentArchDataset(Path("runs/upstream/AgentArch"), "requesting_time_off")
case = dataset.cases()[0]  # only ID and goal, no expected answers
session = dataset.session(case["id"])
registry = session.registry
instructions = session.instructions
provenance = dataset.provenance
```

The loader checks the Git revision and compares both input files against Git's
pinned contents, normalizing Windows newlines. It records their SHA-256 fingerprint.
There are 60 time-off and 50 routing cases at this revision. A session owns an isolated
tool-call history. All tools require the explicit `agentarch.mock` permission.

Behavior matches the pinned mock interface: responses are looked up by record ID
and tool name, not calculated from tool arguments. Repeated tool names use the last
definition, matching upstream. Tools flagged `skip_automatic_tool_registration`
return the upstream invalid-tool response. `finish` returns a message object.
Output schemas intentionally accept JSON because upstream descriptive response types
can conflict with mock values. Query/modify declarations still control safe retries.

`session.grade(run_metrics)` accepts the **official upstream** `agent_arch.metrics.run_metrics`
function from the pinned checkout, in an environment with its grading dependencies
installed (including pandas, numpy, pydantic and PyYAML). It supplies the official
configuration, isolated call trace, withheld ground truth, `single_agent` mode and
disabled thinking tools. It does not reimplement the grader or send labels to a model.
Raw histories stay in memory; do not commit exports. Grader output may contain task
data, so store it only under ignored `runs/`.

Validated locally: both datasets loaded; a finish-only compatibility trace was
accepted by the actual upstream grader and returned its 22 metric fields. This
was **not a model benchmark run**, and is not reported as task success.
An October 5 cross-check also matched all 38 non-finish tool responses for case 1
across both workflows against the upstream mock registry. On Windows, invoke the
upstream Python process with `-X utf8`: its default-encoding JSON loader can otherwise
decode Unicode mock text differently. Orqen reads these pinned inputs as UTF-8.
The SDK now supports application-owned observation-driven stages through
`WorkflowRunner`; this adapter alone still does not establish that a model can
solve conditional enterprise workflows.
Proposal/review planning is also not equivalent to AgentArch's orchestrator modes.

Set `ORQEN_AGENTARCH_CHECKOUT` to the pinned checkout to run the optional integration
tests. CI fetches this exact revision for these tests. Unit tests run offline otherwise.

The [bounded pilot runner](agentarch-pilot.md) now connects whole-plan and
observation-driven execution to the official grader. See [evaluation evidence](agentarch-results.md)
for the all-case negative controls and subsequent pilot results.
