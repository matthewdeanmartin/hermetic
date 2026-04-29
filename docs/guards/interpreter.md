# Interpreter Mutation Guard

Activated by `--no-interpreter-mutation` (CLI) or
`block_interpreter_mutation=True` (API). Implemented in
`hermetic/guards/interpreter.py`.

## What it patches

| Surface | What happens |
|---|---|
| `os.chdir`, `os.fchdir` | Blocked. |
| `site.addsitedir` | Blocked. |
| `sys.path`, `sys.meta_path`, `sys.path_hooks` | Replaced with guarded containers that reject mutation. |
| `sys.path_importer_cache` | Replaced with a guarded dict that rejects mutation. |

The goal is to stop code from re-pointing import resolution or changing
the process working directory after the policy is installed.

## What it does *not* catch

- **Whole-object reassignment** like `sys.path = []` from outside the
  guard module.
- **Captured references** to the original mutable objects obtained
  before installation.

## Examples

```bash
hermetic --no-interpreter-mutation -- python tool.py
```

```python
from hermetic import hermetic_blocker

with hermetic_blocker(block_interpreter_mutation=True):
    ...
```
