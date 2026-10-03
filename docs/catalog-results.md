# Catalog coverage experiment

Run date: October 4, 2026. This is an offline development experiment, not a held-out benchmark or model-performance result.

```powershell
.\.venv\isolated\Scripts\python.exe -m orqen.cli evaluate-catalog --output runs/catalog-evaluation.json
```

The packaged fixture contains 12 tools and eight queries spanning several capabilities. Labels include required prerequisite tools, not only the final action. The retriever receives only the query and tool metadata; labels are used afterward for grading.

Dataset SHA-256: `689b3869fefba82c70543b5fb02c943def45179ad48eea11f819cc335437c2de`.

| Policy | Queries with every required tool | Required-tool recall | Mean tools offered | Mean metadata bytes |
| --- | --- | --- | --- | --- |
| Full catalog | 8/8 | 100% | 12 | 1,350 |
| Fixed top-1 | 3/8 | 47.1% | 1 | 113.25 |
| Fixed top-3 | 5/8 | 76.5% | 3 | 341.625 |
| Adaptive cutoff-3 | 6/8 | 82.4% | 3.75 | 421.75 |

Complete coverage means every labeled prerequisite appears in the shortlist. Recall is the number of covered required tools divided by all required tools across the eight queries. Metadata bytes are the UTF-8 size of serialized offered metadata; they are neither tokens nor a monetary cost estimate.

## What failed

For the leave workflow, adaptive retrieval offered `leave_balance`, `leave_submit`, and `refund_policy`, but omitted `employee_find`. Generic overlap on words such as “check” competed with the actual identity prerequisite.

For “Reimburse this purchase after checking the rules,” it offered only `refund_policy`, omitting `charge_find` and `refund_create`. Positive overlap was insufficient to recover the complete workflow. Showing fewer tools reduced metadata but lost necessary actions.

For the underspecified query “Resolve it,” adaptive retrieval showed the complete catalog because there were no lexical matches. This preserved the labeled tools, but it did not resolve the missing task context. Coverage must not be interpreted as success or sufficient information to act.

## Decision

Keep full-catalog planning as the default. Keep fixed and adaptive retrieval as opt-in experimental policies. Do not tune the lexical heuristic against these eight cases and then claim generalization. Planner-requested expansion is available, but the planner may fail to recognize missing prerequisites, so expansion is not a recall guarantee.

The next useful evidence is a frozen, independently authored query set with distractors, synonyms, similar tool names, prerequisite chains, and permission variants, followed by an actual model comparison using identical settings. We have built the transport boundary, not run that model experiment.

## Evaluate another fixture

```powershell
.\.venv\isolated\Scripts\python.exe -m orqen.cli evaluate-catalog --dataset path/to/catalog.json --output runs/custom-catalog.json
```

The dataset must have `name`, `tools`, and `queries`. Each tool needs a unique `name`, `description`, and `capability`. Each query needs a unique `id`, `goal`, and nonempty `required_tools` list whose entries exist in the catalog. The evaluator rejects invalid datasets. It reports tool IDs, missing IDs, counts, sizes, and timings, but excludes query text from the report. Choose identifiers without sensitive content.
