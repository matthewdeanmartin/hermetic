# Agent guide for hermetic

## This is a uv project — use `uv run` for everything

This repo is managed with [uv](https://docs.astral.sh/uv/). The signals:

- `uv.lock` at the repo root
- `.python-version` pins the interpreter
- `.venv/` is the working virtual environment
- Dev dependencies live under `[dependency-groups].dev` in `pyproject.toml`

**Always invoke dev tools via `uv run`.** It activates `.venv/` for that command.

```bash
uv run pytest                # not: python -m pytest
uv run python -m hermetic ... # not: python -m hermetic ...
uv run mypy hermetic
uv run ruff check
```

### Do NOT `pip install` to fix a missing dep

If `pytest` reports `fixture 'mocker' not found` or `ImportError: No module named foo`, the answer is **not** `python -m pip install <pkg>`. That installs into the system Python, hides the real problem, and pollutes the user's global site-packages.

The right responses:

1. **First try `uv run <command>`.** If the dep is already declared and locked, this just works — the previous failure was caused by running the system Python instead of the venv Python.
1. **If the dep truly is missing**, add it the uv way:
   ```bash
   uv add --group dev <pkg>      # for dev/test deps
   uv add <pkg>                  # for runtime deps
   uv sync                       # after editing pyproject.toml manually
   ```
1. **Never** run `pip install` directly against the active Python unless the user explicitly asks.

### Common commands

```bash
uv sync                         # install/refresh all deps from uv.lock
uv run pytest                   # run the test suite
uv run pytest test/test_security/ -v   # run the security bypass tests
uv run python -m hermetic --help
```

## Repo layout pointers

- `hermetic/guards/` — the actual policy enforcement (network, subprocess, filesystem, env, code_exec, imports, interpreter)
- `hermetic/bootstrap.py` — generated `sitecustomize` for foreign-interpreter runs; must stay in parity with each guard's `BOOTSTRAP_CODE` template
- `test/test_security/` — bypass tests; a new bypass class belongs here with a failing test alongside the fix
- `docs/threat-model.md`, `docs/security.md`, `spec/COPILOT_SAYS.md` — what's already known/in-scope/out-of-scope

## Hermetic-specific guidance

- The threat model is explicit: hermetic is **not** a security boundary, it's a noisy guard rail. Don't add complexity claiming otherwise.
- When fixing a network/fs/subprocess guard, mirror the change into the guard's `BOOTSTRAP_CODE` template **and** `hermetic/bootstrap.py` so in-process and bootstrap installs stay in parity (this is a documented source of drift — see `spec/COPILOT_SAYS.md`).
