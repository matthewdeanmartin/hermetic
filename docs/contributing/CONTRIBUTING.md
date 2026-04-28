# Contributing

Thanks for considering a contribution. Hermetic is small and
maintained by one person — issues and pull requests are welcome,
but please read this page first to avoid wasted effort.

## Project goals (and non-goals)

**Goals**

- A predictable, low-surprise sandbox runner for Python console
  scripts.
- A library for in-process guards that are easy to use from
  pytest fixtures and decorator-style code.
- Honest documentation of what is and isn't defended against.
- Zero runtime dependencies.

**Non-goals**

- Defeating a determined adversary with arbitrary code execution.
  Anyone who needs that should use a real sandbox; see [Threat
  Model](../threat-model.md).
- Replacing OS-level isolation. Hermetic complements containers,
  `seccomp`, etc.; it does not replace them.
- Adding runtime dependencies. New features need to fit inside
  the standard library.

If your idea is in the "non-goal" column, please open an issue
to discuss before submitting code.

## Getting set up

```bash
git clone https://gitlab.com/matthewdeanmartin/hermetic
cd hermetic
uv sync                    # installs the dev group
uv run pytest              # run the test suite
uv run mkdocs serve        # preview docs at http://127.0.0.1:8000
```

The `Justfile` and `Makefile` at the repo root encode common
recipes (`just test`, `just docs`, etc.). Either works; pick the
one your shell prefers.

## Project layout

```
hermetic/
├── __init__.py       # public re-exports
├── __main__.py       # `python -m hermetic`
├── cli.py            # argparse, entry point
├── runner.py         # in-process vs bootstrap dispatch
├── resolver.py       # target-name → module/exec resolution
├── blocker.py        # context manager / decorator
├── profiles.py       # named flag bundles
├── bootstrap.py      # AUTO-GENERATED inlined sitecustomize
├── errors.py         # PolicyViolation, BootstrapError
├── util.py           # arg-splitting, which()
└── guards/           # the actual monkey-patches
    ├── network.py
    ├── subprocess_guard.py
    ├── filesystem.py
    └── imports_guard.py

scripts/
└── build_bootstrap.py   # regenerates hermetic/bootstrap.py

spec/
└── secure_secure.md     # security review and roadmap

test/
├── ...                  # unit tests, mirrors hermetic/ layout
└── test_security/       # known-bypass tests
```

## When adding or changing a guard

A change to any guard in `hermetic/guards/` almost always also
needs a change to `hermetic/bootstrap.py` — the bootstrap
sitecustomize ships an inlined copy of the same logic so that it
works without `hermetic` being importable in the target
interpreter.

The workflow:

1. Edit the in-process guard in `hermetic/guards/<name>.py`.
   Each guard module exposes its bootstrap snippet as the
   `BOOTSTRAP_CODE` constant.
2. Update the corresponding `BOOTSTRAP_CODE` block in the same
   file, or extend the in-file generator.
3. Run `python scripts/build_bootstrap.py` to regenerate
   `hermetic/bootstrap.py`.
4. Add tests under `test/test_guards/` for the in-process path
   and (where it differs) under `test/test_security/` for the
   bootstrap path.
5. Update the relevant page under `docs/guards/` if the user-
   visible behavior changed.

The `bootstrap.py` header carries a `WARNING: AUTO-GENERATED`
notice. Do not hand-edit it.

## When adding or changing a flag

1. Add it to the CLI parser in `hermetic/cli.py`.
2. Add it to `GuardConfig` in `hermetic/profiles.py` (and to
   `BlockConfig` in `hermetic/blocker.py` if it should also be
   exposed via `hermetic_blocker(...)`).
3. Wire it through `runner.run()` and the bootstrap flag passing.
4. Document it in `docs/cli-usage.md` and the relevant guard or
   feature page.
5. Consider whether it should appear in any built-in profile.

## Testing

- `uv run pytest` runs the full suite.
- `uv run pytest test/test_security/` runs the known-bypass
  catalogue. These tests assert *both* that bypasses are blocked
  with the relevant guard on, *and* that they would succeed with
  the guard off — so we don't claim to block something the host
  Python doesn't permit anyway.
- New tests should not require network or external services. The
  test suite is run under hermetic in CI.

## Documentation

- Markdown sources live under `docs/`.
- The published site is built by Read the Docs from
  `mkdocs.yml`. Local preview: `uv run mkdocs serve`.
- Keep the prose honest — if a guard is best-effort, say so.
  Overclaiming security guarantees is the worst outcome for this
  project.

## Pull requests

- Small, focused PRs are easier to review than large ones.
- Include a test that fails before your change and passes after.
- Update docs in the same PR if the user-visible behavior
  changes.
- The CI runs lint (`ruff`), type-check (`mypy`), tests, and
  doc build. Please run them locally before pushing.

## Reporting bugs

- File an issue at <https://gitlab.com/matthewdeanmartin/hermetic>.
- Include: hermetic version, Python version, OS, the exact
  command you ran, and the full output (with `--trace` if a
  guard is involved).
- For security-relevant issues, see the [Security](../security.md)
  page first — some issues warrant a private advisory rather than
  a public bug.

## Code of conduct

Be kind. Assume good faith. The maintainer's time is finite.
