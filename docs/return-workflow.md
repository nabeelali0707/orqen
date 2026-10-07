# Conditional returns sandbox

This runnable SDK example models a small refund policy: a paid order may receive
one refund when its age is 0–30 days and its amount is 1–10,000 cents. The next
stage is selected from the inspection result. Customer text is untrusted data and
does not authorize a refund. Both an application permission and confirmation are
required for the write. The fake backend independently checks current eligibility
and the observed version before changing the ledger.

Run without a model, credentials, network connection or payment provider:

```sh
python examples/returns_workflow.py
```

The example exits nonzero if expected behavior is violated. The state grader uses
explicit case labels and checks the actual ledger, refund flag and unchanged order
fields. Tests also corrupt the ledger and propose an ineligible write to establish
that the grader and policy boundary reject those failures.

## Local results, October 7, 2026

Eight public development cases are crossed with four conditions: normal operation,
one transient read failure, lost write response after commit, and stale observation.
All 32 expected-behavior checks passed: 26 verified completions, 3 uncertain write
outcomes requiring reconciliation, and 3 blocked stale writes. No scenario invoked
the write more than once. A safety check passing is not the same as task completion.

These are deterministic synthetic fixtures authored alongside the implementation.
They are not independent held-out tasks, model trials, payment integration tests
or AgentArch benchmark results. Their purpose is to check conditional execution,
policy enforcement, independent state verification and conservative fault handling.

## Limits

The ledger and idempotency keys exist only in memory. The backend's check-and-write
operation has no await point and assumes a single event loop. It is not a durable
transaction, cross-process lock or production payment adapter. A real integration
must provide atomic version checks, persistent idempotency keys, reconciliation
queries and domain-specific rules. The runner itself never retries uncertain writes.
