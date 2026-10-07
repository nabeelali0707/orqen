# SDK release readiness

The current package is an **alpha research SDK**, not a validated claim of improved
agent reasoning or a production service. Python metadata now labels that maturity
explicitly. Publishing a package and establishing a research result are separate
decisions.

## Checked locally on October 7, 2026

- Full suite with the pinned AgentArch checkout: 249 passing tests.
- Conditional refund regression: 32 expected-behavior checks, including uncertain
  and blocked outcomes; see `return-workflow.md` for the separate completion count.
- Wheel built offline with locally installed setuptools 81.0.0.
- Wheel member audit found the required runtime assets and no prohibited paths or
  matching provider-key patterns. Pattern checks are not a complete secret audit.
- Installed wheel imported from a temporary directory outside the source tree and
  passed all 32 workflow checks. No dependency download or inference was required.

Reproduce the packaging checks in an environment with setuptools, pip and the
runtime dependencies already installed:

```sh
python -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist
python scripts/check_wheel.py dist/orqen-0.1.0-py3-none-any.whl
```

The smoke test intentionally reuses installed dependencies. It does not establish
clean dependency resolution across all supported Python versions. CI now builds
and checks the wheel on its Python 3.11–3.14 matrix; those remote runs are not yet
evidence for these unpushed commits.

## Gates before publication

1. Choose and add the owner's distribution license; no license is currently declared.
2. Run the updated CI matrix on the exact release commit and resolve any failures.
3. Verify package-name availability and publishing-account access when publication
   is authorized. No registry credentials are needed for local wheel validation.
4. Use alpha release positioning and preserve the measured failures and limits.
   Do not describe this package as a validated enterprise or adaptive-reasoning solution.

## Gates for the stronger research or production claim

Research needs independently graded model runs on a frozen task set, equivalent
baselines, failure analysis, and uncertainty/cost/latency reporting. Public fixtures
and tests do not satisfy that gate. Production needs a chosen real workflow and
backend, persistent idempotency and reconciliation, operational retention, token
management, TLS, deployment and workload-specific acceptance testing. A sandbox
ledger and local authenticated dashboard do not satisfy that gate.
