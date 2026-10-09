# SDK release readiness

The current package is an **alpha research SDK**, not a validated claim of improved
agent reasoning or a production service. Python metadata now labels that maturity
explicitly. Publishing a package and establishing a research result are separate
decisions.

## Checked locally on October 7, 2026

- Full suite with the pinned AgentArch checkout: 266 passing tests.
- Conditional refund regression: 32 expected-behavior checks, including uncertain
  and blocked outcomes; see `return-workflow.md` for the separate completion count.
- Wheel built offline with locally installed setuptools 81.0.0.
- Source archive includes the SDK guides, runnable examples and wheel checker.
  Its path/key-pattern audit passed, and a wheel rebuilt from that source archive
  passed the installed-wheel smoke check.
- Wheel member audit found the required runtime assets and no prohibited paths or
  matching provider-key patterns. Pattern checks are not a complete secret audit.
- Installed wheel imported from a temporary directory outside the source tree and
  passed all 32 workflow checks. No dependency download or inference was required.
- One constrained local Llama planning attempt passed the unchanged synthetic
  verifier after an unconstrained attempt failed on naming. This is one-case
  compatibility evidence only; see `model-results.md` for identities and limits.
- Interrupted experiments now retain completed metadata checkpoints and explicitly
  mark unavailable identity verification rather than silently discarding results.

Reproduce the packaging checks in an environment with setuptools, pip and the
runtime dependencies already installed:

```sh
python -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist
python scripts/check_wheel.py dist/orqen-0.1.0-py3-none-any.whl
```

The smoke test intentionally reuses installed dependencies. It does not establish
clean dependency resolution across all supported Python versions. CI now builds
and checks the wheel on its Python 3.11–3.14 matrix; those remote runs are not yet
evidence for later release-preparation changes. The October 7 source at `9a6d08a`
passed [remote CI](https://github.com/nabeelali0707/orqen/actions/runs/37605491345).

## Gates before publication

October 9 preparation: `0.1.0a1`, MIT metadata/license, release notes, and the
manual TestPyPI/PyPI workflow are implemented. All 273 tests passed at this
milestone, and the alpha source archive produced an audited wheel that passed
the installed-package smoke. Local Twine is unavailable; the workflow runs
`twine check --strict` before uploading. The publishing workflow has not run.

After the benchmark runner and source-archive guards were added, the final local
suite passed **283 tests**. The rebuilt `0.1.0a1` wheel passed metadata/license
identity checks, file/key-pattern audits, all 32 installed workflow checks, and
the installed CLI version check. Builds used the installed setuptools backend
and `pip wheel --no-index --no-deps --no-build-isolation`; the separate `build`
frontend and Twine were not available locally. Dependency resolution and the new
publishing workflow still require the release CI run. No distribution was uploaded.

1. Review the newly added MIT license and `0.1.0a1` release notes.
2. Push the release-preparation commit and pass CI on the exact tagged release.
3. Configure the owner's PyPI/TestPyPI Trusted Publishers and run the prepared
   manual publishing workflow. See `publishing.md` for the exact account fields.
4. Verify registry installation, then publish with alpha positioning and preserve
   the measured failures and limits.
   Do not describe this package as a validated enterprise or adaptive-reasoning solution.

## Gates for the stronger research or production claim

Research needs independently graded model runs on a frozen task set, equivalent
baselines, failure analysis, and uncertainty/cost/latency reporting. Public fixtures
and tests do not satisfy that gate. Production needs a chosen real workflow and
backend, persistent idempotency and reconciliation, operational retention, token
management, TLS, deployment and workload-specific acceptance testing. A sandbox
ledger and local authenticated dashboard do not satisfy that gate.
