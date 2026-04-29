# Environment Guard

Activated by `--no-environment` / `--no-env` (CLI) or
`block_environment=True` (API). Implemented in
`hermetic/guards/environment.py`.

## What it patches

| Surface | What happens |
|---|---|
| `os.getenv` | Blocked. |
| `os.putenv`, `os.unsetenv` | Blocked. |
| `os.environ`, `os.environb` | Replaced with guard mappings that reject reads and writes. |

This is meant for cases where secrets live in environment variables or
where you don't want wrapped code to mutate child-process state.

## What it does *not* catch

- **Captured references** to the original `os.environ` mapping or
  `os.getenv` taken before hermetic installs.
- **Process state already copied out** into ordinary Python variables.

## Examples

```bash
hermetic --no-environment -- python my_tool.py
```

```python
from hermetic import hermetic_blocker

with hermetic_blocker(block_environment=True):
    ...
```
