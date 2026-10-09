# Publishing Orqen 0.1.0a1

This is an alpha SDK with an MIT license. It is not a validated claim of adaptive
reasoning superiority or a production service. Release notes are in `CHANGELOG.md`.
The workflow is prepared but no package has been uploaded.

## One-time account configuration

Sign in to your own PyPI and TestPyPI accounts. Their accounts and publishers are
separate. Configure a pending Trusted Publisher on each registry:

| Field | Value |
| --- | --- |
| PyPI project name | `orqen` |
| GitHub owner | `nabeelali0707` |
| GitHub repository | `orqen` |
| Workflow filename | `publish.yml` |
| Environment | `testpypi` on TestPyPI; `pypi` on PyPI |

Create the matching GitHub repository environments. Environment protection rules
can require an owner review before publication. No permanent PyPI API token is
needed. Configuring a pending publisher does not reserve a project name; the registry
must accept the name when the first upload occurs.

References: [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
and [pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Release sequence

1. Review the MIT license and alpha release notes, then push the release commit.
2. After CI passes on that commit, create and push tag `v0.1.0a1` on that exact commit.
3. In GitHub Actions, run **Publish alpha SDK** with that tag and `testpypi`.
4. Verify installation from TestPyPI in a fresh environment.
5. Run the same workflow with the same tag and `pypi` for the public release.

Tagging or pushing alone never publishes. The workflow checks tag/version/license
identity, builds a source archive and wheel, validates their metadata, audits and
smoke-tests the wheel, and runs the test suite against the installed wheel on Python
3.11–3.14. Only then does the separate OIDC-enabled job upload those artifacts.
The build and test jobs do not receive publishing permission.

## Local preparation, no upload

Use a fresh output directory so old versions cannot be uploaded accidentally:

```sh
python scripts/check_release.py --tag v0.1.0a1
python -m build --outdir dist/alpha
python -m twine check --strict dist/alpha/*
python scripts/check_release.py --tag v0.1.0a1 --artifacts dist/alpha
python scripts/check_wheel.py dist/alpha/orqen-0.1.0a1-py3-none-any.whl
```

The release checker rejects stale or extra files in the artifact directory. Do not
upload the older development wheels in the top-level `dist/` directory.

If working offline without the `build` frontend but with setuptools already
installed, the source/wheel build can instead use:

```sh
python -c "from setuptools.build_meta import build_sdist; build_sdist('dist/alpha')"
python -m pip wheel dist/alpha/orqen-0.1.0a1.tar.gz --no-index --no-deps --no-build-isolation --wheel-dir dist/alpha
```

This fallback does not replace the publishing workflow's strict Twine check or
its clean installation matrix.

## TestPyPI installation check (after upload)

In a fresh virtual environment, install dependencies from PyPI and then request
only Orqen from TestPyPI. This avoids mixing package indexes for dependency lookup:

```sh
python -m pip install "jsonschema>=4.23,<5"
python -m pip install --index-url https://test.pypi.org/simple/ --no-deps orqen==0.1.0a1
orqen --version
orqen evaluate --repetitions 1
```

Public installation after the PyPI upload is `python -m pip install orqen==0.1.0a1`.
Published versions should be treated as immutable: make a new alpha version for a
changed artifact rather than reusing a version whose upload partially succeeded.
