# Bootstrap Mode

When the target you ask hermetic to run lives in a *different* Python
interpreter than hermetic itself — for example, a `pipx`-installed
console script — hermetic switches to **bootstrap mode**: it
re-launches the target under its own interpreter with a generated
`sitecustomize.py` that installs the same guards before any user
code runs.

You don't normally need to know about this. It just works. This
page exists for when it doesn't.

## When bootstrap mode triggers

After resolving the target name, hermetic compares its interpreter
to `sys.executable`:

| Resolved target's interpreter | Mode |
|---|---|
| Same as `sys.executable` (same `realpath`) | In-process |
| Different from `sys.executable` | Bootstrap |
| Target is `python`, `py.exe`, or any script with a Python shebang on PATH | Bootstrap (with the resolved interpreter) |

`pipx` installs each tool into its own venv, so a `pipx`-installed
target almost always triggers bootstrap mode when hermetic itself is
installed in the parent environment (or in a different `pipx` venv).

## How it works

1. Hermetic writes a `sitecustomize.py` to a fresh temp directory.
   The file contains an inlined, dependency-free copy of the
   guard installation code.
2. The selected guards are serialized as JSON into the environment
   variable `HERMETIC_FLAGS_JSON`.
3. The temp directory is prepended to `PYTHONPATH`.
4. The target executable is launched (POSIX: `os.execve` —
   replaces the current process; Windows: `subprocess.run` then
   propagate exit code).
5. The target interpreter starts up, `sitecustomize.py` runs
   automatically (Python's standard startup mechanism), reads
   `HERMETIC_FLAGS_JSON`, installs the guards, then deletes the
   env var so it doesn't leak to grandchild processes.
6. The target's entry point runs as it normally would, now with
   guards active.

The temp directory is **not** cleaned up. It's a few KB of text
sitting in your system temp dir; the OS removes it on the next
reboot.

## Implications for the user

- The target sees a clean `sys.argv`: exactly the tokens after `--`.
- The target's exit code is propagated.
- `PolicyViolation` from the guards prints
  `hermetic: blocked action: ...` to stderr and exits with code `2`,
  via a custom `sys.excepthook` installed by the bootstrap.
- `HERMETIC_FLAGS_JSON` is consumed and removed from the
  environment by the bootstrap, so subprocesses launched by the
  target (if `--no-subprocess` is not set) **do not inherit the
  guards**. If you need cascading guards, set `--no-subprocess`
  too.

## Why two implementations?

The in-process guards (under `hermetic/guards/`) and the bootstrap
sitecustomize (in `hermetic/bootstrap.py`) are **two implementations
of the same policy**. The bootstrap version is intentionally
self-contained: it doesn't import `hermetic`, because `hermetic`
might not be installed in the target interpreter. It is generated
from the in-process guard code via `scripts/build_bootstrap.py`,
and a header in `bootstrap.py` warns against editing it by hand.

If you change a guard's behavior, change both copies — or
regenerate the bootstrap from the guard sources.

## Platform differences

### POSIX

`os.execve` replaces the current process, giving the target the
same PID and seamless I/O handoff. Exit code propagation is
automatic.

### Windows

`os.execve` exists on Windows but is not a true process
replacement — it spawns and the parent exits, which breaks
Ctrl-C handling and exit-code propagation. Hermetic uses
`subprocess.run` instead and explicitly forwards the child's
return code. The behavior is almost indistinguishable from
POSIX `execve` for most users.

If the target executable is missing, hermetic exits with code
`127` (the conventional "command not found" code).

## Debugging bootstrap mode

Add `--trace` and you'll see guard installation messages from the
bootstrap in stderr just as you would in-process:

```bash
hermetic --no-network --trace -- some-pipx-tool --foo
```

To see whether bootstrap mode was actually used, you can poke at
`PYTHONPATH` from inside the target. A path entry like
`/tmp/hermetic_site_XXXXXX` indicates bootstrap.

If something looks wrong:

1. Check that the target's interpreter has read access to the
   temp directory.
2. Check that the target isn't overriding `PYTHONPATH` itself.
3. Make sure the target uses an entry-point `sitecustomize` —
   some unusual Python distributions disable site customization.

## Limitations

- The bootstrap inlines a snapshot of the guards. Newly added
  guards don't appear in bootstrap mode until
  `scripts/build_bootstrap.py` is re-run.
- Children of the bootstrapped process do **not** inherit guards
  unless they happen to share the `sitecustomize` directory on
  their `PYTHONPATH` (which they don't, by default — the env var
  is consumed and removed). Combine with `--no-subprocess` to
  prevent guarded targets from spawning unguarded children.
- The temp directory is left on disk.
