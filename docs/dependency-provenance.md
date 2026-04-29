# Dependency Provenance

Hermetic's runtime dependency list is intentionally short:

```toml
# pyproject.toml
[project]
dependencies = []
```

That's the full list. **Zero** third-party packages are required to
run hermetic. Everything is implemented against the Python
standard library, on purpose:

- Less to audit.
- Less to break when an upstream package changes.
- No transitive supply-chain exposure to ship.

## What is in the dev dependency group

The dev group (`pyproject.toml` `[dependency-groups].dev`) is a
larger pile, but none of it is shipped to end users. Highlights:

| Group | Packages | Purpose |
|---|---|---|
| Test | `pytest`, `pytest-cov`, `pytest-xdist`, `pytest-randomly`, `pytest-sugar`, `pytest-mock`, `pytest-asyncio`, `pytest-timeout`, `pytest-unused-fixtures`, `hypothesis`, `detect-test-pollution` | Test execution and quality. |
| Lint / type | `ruff`, `pylint`, `mypy`, `vermin`, `types-toml`, `types-requests` | Static checks. |
| Docs | `mkdocs`, `mkdocs-material`, `mkdocs-material-extensions`, `mkdocs-print-site-plugin`, `mkdocstrings[python]`, `mdformat`, `linkcheckmd`, `interrogate`, `pdoc3`, `pydoctest`, `codespell`, `pyenchant`, `strip-docs` | Documentation generation and lint. |
| Build / release | `hatchling`, `troml-dev-status`, `jiggle_version`, `metametameta`, `gha-update`, `pyclean`, `git2md` | Packaging and metadata management. |
| Demo / dogfood | `httpie`, `cffi` | Used in examples and exploit tests. |

These are pinned via `uv.lock` for reproducible dev environments,
not pinned via `pyproject.toml` for end users.

## Build provenance

- **Build backend**: `hatchling`. Configured via the standard
  `[build-system]` table in `pyproject.toml`.
- **Wheel and sdist contents**: explicitly declared. Only
  `hermetic/**/*.py`, `hermetic/py.typed`, the project README,
  and the LICENSE are included. No build tooling, no test
  fixtures, no docs.
- **Lockfile**: `uv.lock` committed at the repo root for the dev
  environment. End users' installs are unconstrained beyond the
  Python version requirement (`>=3.9`).

## Doc build provenance

The Read the Docs build pulls a separate, smaller requirement
list:

```text
# docs/requirements.txt
mkdocs
mkdocs-get-deps
mkdocstrings[python]
mkdocs-material
mkdocs-material-extensions
mkdocs-print-site-plugin
pymdown-extensions>=10.16.1   # CVE pin via Snyk
urllib3>=2.6.3                 # CVE pin via Snyk
```

The `pymdown-extensions` and `urllib3` pins are direct vulnerability
mitigations even though hermetic itself doesn't import them — they
arrive transitively via mkdocs.

## How to verify a release

1. Install from a fresh virtual environment:
   ```bash
   python -m venv /tmp/hverify
   /tmp/hverify/bin/pip install hermetic-seal==<VERSION>
   ```
1. Confirm zero dependencies installed beyond `hermetic-seal`:
   ```bash
   /tmp/hverify/bin/pip list
   ```
   You should see only `pip`, `setuptools`, `hermetic-seal`, and
   nothing else hermetic-related.
1. Confirm the version:
   ```bash
   /tmp/hverify/bin/hermetic --version
   ```
1. Cross-check the wheel contents against the published release:
   ```bash
   /tmp/hverify/bin/python -m zipfile -l "$(pip show -f hermetic-seal | head)"
   ```

## Reporting supply-chain concerns

If you observe an unexpected runtime dependency in a release, an
anomalous file in the wheel, or a published version that doesn't
match the GitLab tag, please report it via the channels in
[Security](security.md).
