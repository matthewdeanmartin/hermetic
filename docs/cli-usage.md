# CLI Usage

```text
hermetic [HERMETIC_OPTS] -- <TARGET> [TARGET_ARGS...]
```

The `--` separator is **mandatory** when invoking a target. Hermetic
parses everything before `--` as its own flags; everything after is
passed verbatim to the target. This avoids any flag collision between
hermetic and the program you're wrapping, even if that program uses
its own `argparse` with positional arguments.

If you pass `-h`, `--help`, or `--version` and no `--`, hermetic
treats the call as help-only and prints help, then exits.

## Targets

`<TARGET>` is resolved in this order:

1. **`module:attr`** — `pkg.module:callable`. Imports the module and
   invokes the callable, or runs the module as `__main__` if `attr`
   is not callable.
1. **Console script** — anything registered under
   `console_scripts` entry points in any installed distribution.
   `http`, `black`, `pytest`, `mytool`, etc.
1. **Executable on PATH** — `python`, `py.exe`, or any script with a
   Python shebang.
1. **Module name fallback** — runs as `python -m <TARGET>`.

If the resolved console script lives in a *different* Python
interpreter (typical for `pipx`-installed tools), hermetic switches
to [Bootstrap Mode](bootstrap-mode.md) and re-launches the target
under its own interpreter with a generated `sitecustomize.py` that
applies the same guards.

## Flags

### Network

| Flag | Effect |
|---|---|
| `--no-network` | Disable outbound networking — `socket.connect`, `getaddrinfo`, `gethostbyname`, `ssl.SSLContext.wrap_socket`, `socketpair`, `fromfd`, `fromshare`. Bind to non-loopback also denied. |
| `--allow-localhost` | When `--no-network` is on, permit connections to `127.0.0.1`, `::1`, `localhost`, `0.0.0.0`. |
| `--allow-domain DOMAIN` | When `--no-network` is on, permit connections to `DOMAIN` and `*.DOMAIN` (suffix match). Repeatable. |

Cloud metadata endpoints (`169.254.169.254`,
`metadata.google.internal`, `fd00:ec2::254`, `fe80::a9fe:a9fe`,
`100.100.100.200`) are always denied. `--allow-domain` cannot
override this.

See [Network Guard](guards/network.md) for the full surface.

### Subprocess

| Flag | Effect |
|---|---|
| `--no-subprocess` | Block `subprocess.Popen/run/call/...`, `os.system`, `os.exec*`, `os.spawn*`, `os.fork`, `posix_spawn`, `asyncio.create_subprocess_*`, `multiprocessing.Process.start`, `_posixsubprocess.fork_exec`. |

See [Subprocess Guard](guards/subprocess.md) for the full surface.

### Filesystem

| Flag | Effect |
|---|---|
| `--fs-readonly` | Deny all writes (`open(..., "w"/"a"/"x"/"+")`, `os.rename`, `os.remove`, `pathlib.Path.write_text`, `shutil.copy*`, `shutil.move`, `shutil.rmtree`, etc.). Reads anywhere are still permitted. |
| `--fs-readonly=ROOT` | Same as above, plus reads must lie under `ROOT` (resolved via `os.path.realpath`, so symlinks are followed before the check). |

See [Filesystem Guard](guards/filesystem.md) for the full surface.

### Environment

| Flag | Effect |
|---|---|
| `--no-environment`, `--no-env` | Block `os.getenv`, `os.environ[...]`, `os.putenv`, `os.unsetenv`, and mapping-style environment access. |

See [Environment Guard](guards/environment.md) for the full surface.

### Dynamic code execution

| Flag | Effect |
|---|---|
| `--no-code-exec` | Block `eval`, `exec`, direct `compile(...)` calls, and `runpy.run_module` / `runpy.run_path`. Imports still work. |

See [Dynamic Code Guard](guards/dynamic-code.md) for the full surface.

### Import policy

| Flag | Effect |
|---|---|
| `--deny-import NAME` | Deny importing `NAME` and its submodules. Repeatable. |
| `--block-native` | Refuse to load native extension modules (`.so`/`.pyd`). Refuse to import `ctypes`, `_ctypes`, `cffi`, `_cffi_backend`. Patch `ctypes.CDLL`, `ctypes.PyDLL`, `cffi.FFI`, etc. on already-loaded copies. When combined with `--no-subprocess`, also block `sh`, `pexpect`, `plumbum`, `sarge`, `delegator`. |

See [Import Policy Guard](guards/import-policy.md) and [Native Imports Guard](guards/native-imports.md) for the full surface.

### Interpreter mutation

| Flag | Effect |
|---|---|
| `--no-interpreter-mutation` | Block `os.chdir`, `os.fchdir`, `site.addsitedir`, and mutation of `sys.path`, `sys.meta_path`, `sys.path_hooks`, and `sys.path_importer_cache`. |

See [Interpreter Mutation Guard](guards/interpreter.md) for the full surface.

### Profiles

| Flag | Effect |
|---|---|
| `--profile NAME` | Apply a named bundle of flags. Repeatable. Profiles compose by union. |

Built-in profiles: `block-all`, `net-hermetic`, `exec-deny`,
`fs-readonly`, `block-native`. `block-all` now also enables the
environment, dynamic-code, and interpreter-mutation guards. See [Profiles](profiles.md).

### Other

| Flag | Effect |
|---|---|
| `--trace` | Print one structured line to stderr for every blocked action. |
| `--seal` | Once installed, refuse to uninstall. Raises the bar against one-line bypass; not bulletproof. See [Sealed Mode](sealed-mode.md). |
| `--version` | Print version and exit. |
| `-h`, `--help` | Print help and exit. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` (or anything the target returns) | Target ran to completion. The target's exit code is propagated. |
| `2` | A guard blocked an action — `PolicyViolation` raised. |
| `1` | Hermetic itself failed (bad flags, target not found, bootstrap error). |
| `127` | (Windows bootstrap mode only) Target executable not found. |

## Examples

Block network for HTTPie:

```bash
hermetic --no-network -- http https://example.com
```

Allow only localhost; block subprocess; serve a dev app:

```bash
hermetic --no-network --allow-localhost --no-subprocess -- devserver --port 8000
```

Lock everything down for a one-shot data analyzer:

```bash
hermetic --profile block-all -- my_analyzer.py --input data.csv
```

Sandbox-rooted read-only filesystem:

```bash
hermetic --fs-readonly=./sandbox -- python my_script.py
```

Use a `pipx`-installed tool with sandboxing applied to its venv:

```bash
hermetic --no-network -- http https://example.com
# hermetic detects foreign Python, injects sitecustomize, execs the script
```

Explicit `module:attr` form:

```bash
hermetic --no-network -- httpie.core:main https://example.com
```
