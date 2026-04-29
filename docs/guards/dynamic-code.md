# Dynamic Code Guard

Activated by `--no-code-exec` (CLI) or `block_code_exec=True` (API).
Implemented in `hermetic/guards/code_exec.py`.

## What it patches

| Surface | What happens |
|---|---|
| `eval` | Blocked. |
| `exec` | Blocked. |
| `compile` | Blocked for direct calls. Import machinery is allowed to keep compiling normal modules. |
| `runpy.run_module`, `runpy.run_path` | Blocked for user code. Hermetic's own in-process launcher still uses `runpy` internally. |

This guard is aimed at plugin and LLM scenarios where runtime code
generation is itself suspicious.

## What it does *not* catch

- **Existing code objects** that were compiled before the guard was
  installed.
- **Import-time compilation** for normal module loading. Hermetic
  allows this on purpose so guarded programs can still import Python
  modules.

## Examples

```bash
hermetic --no-code-exec -- python tool.py
```

```python
from hermetic import with_hermetic

@with_hermetic(block_code_exec=True)
def main():
    ...
```
