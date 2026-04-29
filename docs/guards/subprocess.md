# Subprocess Guard

Activated by `--no-subprocess` (CLI) or `block_subprocess=True` (API).
Implemented in `hermetic/guards/subprocess_guard.py`.

## What it patches

The standard-library entry points first:

| Module | Functions patched |
|---|---|
| `subprocess` | `Popen`, `run`, `call`, `check_output`, `check_call`, `getoutput`, `getstatusoutput` |
| `os` | `system`, `execv`, `execve`, `execl`, `execle`, `execlp`, `execlpe`, `execvp`, `execvpe`, `fork`, `forkpty`, `spawnl{,e,p,pe,v,ve,vp,vpe}`, `posix_spawn`, `posix_spawnp`, `startfile` |
| `asyncio` | `create_subprocess_exec`, `create_subprocess_shell` |
| `multiprocessing` | `Process.start` |

Then the C-level primitives (best-effort, POSIX-only where applicable):

| Module | Functions patched |
|---|---|
| `_posixsubprocess` | `fork_exec` (the underlying primitive `subprocess.Popen` calls on POSIX) |
| `posix` | `fork`, `forkpty`, `system`, `posix_spawn`, `posix_spawnp` |
| `pty` | `fork`, `spawn`, `openpty` |
| `_winapi` | `CreateProcess` (the underlying primitive `subprocess.Popen` calls on Windows) |

Anyone who reimplements `subprocess.Popen` from scratch reaches
`_posixsubprocess.fork_exec` on POSIX or `_winapi.CreateProcess`
on Windows — patching both closes the obvious bypass on either
platform.

## Subprocess-replacement libraries

Several third-party libraries wrap `subprocess` and capture
references to it at import time. If they were already imported when
hermetic installed, patching `subprocess.Popen` doesn't reach them.

When you combine `--no-subprocess` **with** `--block-native`,
hermetic also denies imports of:

- `sh`
- `pexpect`
- `plumbum`
- `sarge`
- `delegator`

If you use `--no-subprocess` alone (the common test-fixture case),
these libraries are not blocked from importing — but their actual
exec calls still go through `subprocess.Popen` or `os.exec*`, which
are patched.

## What it does *not* catch

- **Captured-reference bypass**. Libraries that did `from subprocess
  import Popen` before hermetic ran hold the unpatched callable.
  This is the same class of issue as the network guard.
- **Shell metacharacter use through other allowed mechanisms**. If
  you allow `os.system` (you can't with this guard, but
  hypothetically) or your tool already invokes a shell directly via
  some C extension, hermetic doesn't see it.
- **Windows `CreateProcess`** at the C level — the `subprocess`,
  `os.system`, and `os.spawn*` surface is patched, but a custom C
  extension that calls `CreateProcessW` directly bypasses.

## Tracing

```text
[hermetic] blocked subprocess reason=no-subprocess
```

Hermetic deliberately does **not** log the `argv` of blocked calls
in trace output: the `argv` may contain secrets passed via command
line. The block message names the API; the rest is in the
exception's traceback if you need it.

## Examples

```bash
# Test wants to be sure the code under test isn't shelling out.
hermetic --no-subprocess -- pytest tests/
```

```bash
# Belt-and-braces for an LLM tool runner.
hermetic --no-subprocess --block-native -- python run_agent.py
```

```python
# Programmatic: block subprocess for one section.
from hermetic import hermetic_blocker

with hermetic_blocker(block_subprocess=True):
    import subprocess
    subprocess.run(["echo", "hi"])  # raises PolicyViolation
```
