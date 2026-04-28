# Installation

`hermetic` is published on PyPI as **`hermetic-seal`**. The Python module
and CLI are both named `hermetic`.

## Requirements

- Python **3.9 or newer**.
- No runtime dependencies. Everything is implemented against the Python
  standard library.
- Linux, macOS, and Windows are supported. A handful of guard surfaces
  are POSIX-only (e.g. `os.fork`); they are skipped silently on Windows.

## Install with pip

```bash
pip install hermetic-seal
```

## Install with uv

```bash
uv add hermetic-seal             # add to a project
uv tool install hermetic-seal    # global, isolated install
```

## Install with pipx

```bash
pipx install hermetic-seal
```

`pipx` puts `hermetic` in its own virtualenv. This is fine — hermetic
will detect when the *target* you ask it to run lives in a different
interpreter (a different `pipx` venv, for example) and will switch into
[Bootstrap Mode](bootstrap-mode.md) to wrap it correctly.

## Verify the install

```bash
hermetic --version
hermetic --help
```

A bare `hermetic` (with no `--` and no target) prints help and exits 0.

## Adding to a project as a dev dependency

For unit-test use, you usually want hermetic only at test time:

```toml
# pyproject.toml
[dependency-groups]
dev = [
    "hermetic-seal",
    # ...
]
```

Or in a `requirements-dev.txt`:

```text
hermetic-seal
```

## Uninstall

```bash
pip uninstall hermetic-seal
```

There is no machine state left behind — guards are installed at process
start and torn down at process exit.
