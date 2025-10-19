# PEP: Hermetic — a user-space sandbox runner for Python console scripts

## Abstract

Define a standard CLI runner, **hermetic**, that executes an existing Python console script (e.g., `http`, `black`,
`pytest`) inside a constrained environment. Constraints are enabled via first-class flags (`--no-network`,
`--no-subprocess`, etc.) and are enforced by Python-level guards installed *before* the target loads. `hermetic` must (
a) resolve console-script entry points, (b) avoid CLI flag collisions between itself and the target, (c) interoperate
with `argparse`, and (d) support tools installed by **pip** or **pipx** using the same entry point the user would
normally invoke.

## Motivation

* Tests and reproducible runs often need “air-gapped” execution without changing the target program.
* Current approaches rely on pytest fixtures, per-tool flags, or OS sandboxes; none provide a portable, zero-code-change
  wrapper for arbitrary Python CLIs.
* Developers need predictable CLI UX: `hermetic [sandbox flags] -- target [target flags]`.

## Rationale / Non-Goals

* **User-space enforcement**: fast feedback and portability. Does not claim to defeat a determined adversary; pair with
  OS isolation for high-risk scenarios.
* **No code edits** to the target; prefer entry-point resolution and early import hooks.
* **Console-script fidelity**: call the same entry point a user would call on the command line (pip or pipx installs).

## Terminology

* **Target**: the Python console script or module being run (e.g., `httpie`).
* **Guard**: a patch that disables or filters capabilities (e.g., sockets).
* **Profiles**: named sets of guards.

---

## Specification

### CLI Syntax

```
hermetic [HERMETIC_OPTS] -- <TARGET> [TARGET_ARGS...]
```

* `--` is **required** to separate hermetic’s options from the target’s options.
* A compatibility fallback (heuristic split) MAY be implemented, but tools **SHOULD** document and rely on `--`.

#### Hermetic options (minimum set)

* `--no-network`
  Disables outbound networking by patching `socket.socket`, `socket.create_connection`, DNS (`socket.getaddrinfo`), and
  TLS wrapping; optionally blocks high-level HTTP stacks for better error reporting.
* `--no-subprocess`
  Blocks `subprocess.*`, `os.system`, `asyncio.create_subprocess_*`, and related exec/spawn calls.
* `--fs-readonly[=PATH]`
  Denies writes; reads allowed only under CWD or optional `PATH`.
* `--allow-localhost`
  Exception for `127.0.0.1`, `::1`, `localhost`.
* `--allow-domain DOMAIN` (repeatable)
  Allowlist host substring match (PoC: substring; later: exact/regex).
* `--profile NAME` (repeatable)
  Shorthand bundles (e.g., `net-hermetic`, `exec-deny`, `fs-readonly`).
* `--trace`
  Log blocked calls and decisions to `stderr`.
* `--strict-imports`
  Deny loading native extensions (`.so/.pyd`) and FFI modules (`ctypes`, `cffi`).

Non-normative future flags: `--env-scrub`, `--deny-host`, `--deny-ip`, `--clock-freeze`, etc.

### Argument Separation and `argparse`

* Hermetic **MUST** parse only its flags up to the first `--`.
* After `--`, **all** tokens are passed verbatim to the target.
* Rationale: guarantees zero collision even when target uses `argparse` with complex/positional forms.
* Implementation guidance: use `sys.argv.index('--')` to split; avoid `parse_intermixed_args` for the hermetic side to
  keep split unambiguous.

### Target Resolution (entry points)

Given `<TARGET>`:

1. **Module spec**: if `<TARGET>` contains `:` treat as `pkg.module:callable`. Import and call the callable (if
   callable) or run module as `__main__`.
2. **Console script resolution (preferred)**:

    * Query `importlib.metadata.entry_points(group="console_scripts")`; if an entry point with `name == <TARGET>`
      exists, obtain `module:attr`.
    * Import the module and invoke the callable. If no callable, run module `__main__`.
3. **Module fallback**: if not a known entry point, attempt `runpy.run_module(<TARGET>, run_name="__main__")`.

> **Requirement**: Hermetic MUST install guards **before** importing the target’s module to avoid early side-effects.

### Pip vs Pipx Interoperability

Two execution modes are required:

1. **In-process mode (same environment)**

    * Use the current interpreter and sys.path.
    * Install guards, then import and run the target entry point.

2. **Subprocess bootstrap mode (foreign environment, e.g., pipx venv)**

    * If `<TARGET>` resolves to an executable found on PATH whose shebang points to a *different* Python:

        * Determine target interpreter from the script’s shebang.
        * Prepend an ephemeral directory containing a `sitecustomize.py` that installs hermetic guards based on hermetic
          flags (exported in env, e.g., `HERMETIC_FLAGS=...`).
        * Spawn the target interpreter with `PYTHONPATH=<hermetic_site_dir>:<existing>` so `sitecustomize` executes *
          *before** entry point code.
        * Exec the original console script unchanged.
    * This preserves the “same entry point” semantics users get from pipx (the target still starts via its own console
      script within its venv), while applying guards at interpreter startup.

### Guards (minimum normative patch surface)

* **Network** (`--no-network`)

    * Replace/guard: `socket.socket`, `socket.create_connection`, `socket.getaddrinfo`, `ssl.SSLContext.wrap_socket`.
    * SHOULD provide explicit messages for blocked hosts; MUST block well-known cloud metadata endpoints (
      `169.254.169.254`, `metadata.google.internal`, Azure metadata IP) unless explicitly allowlisted.
* **Subprocess** (`--no-subprocess`)

    * Block: `subprocess.Popen/run/call/check_output`, `os.system`, `os.exec*`, `os.spawn*`,
      `asyncio.create_subprocess_*`.
* **Filesystem (readonly)** (`--fs-readonly[=PATH]`)

    * Forbid write modes in `builtins.open`, `pathlib.Path.open`, `os.open` (+ write/rename/remove APIs).
    * MAY allow writes under a sandbox root (default: deny-all writes).
* **Strict imports** (`--strict-imports`)

    * Replace `importlib.machinery.ExtensionFileLoader` with a loader that raises on native modules.
    * Deny importing `ctypes`, `cffi` by name.
* **Allowlist helpers**

    * `--allow-localhost`, `--allow-domain` modify network guard decisions but MUST NOT implicitly disable other guards.

### Error Model and Exit Codes

* Exit `2` for **blocked action** (policy violation).
* Exit `1` for other runtime errors in hermetic itself.
* Propagate target’s exit code when execution is permitted and completes normally.

### Introspection & Telemetry

* `--trace` prints structured lines to `stderr`:

  ```
  [hermetic] blocked socket.create_connection host=example.com reason=no-network
  [hermetic] blocked subprocess.run argv=['curl','...'] reason=no-subprocess
  ```
* Logging MUST NOT leak secrets (redact env vars and tokens).

### Configuration Sources (lowest to highest precedence)

1. Built-in defaults.
2. Config file (optional): `pyproject.toml` `[tool.hermetic]` or `HERMETIC.toml`.
3. Environment: `HERMETIC_FLAGS`, `HERMETIC_PROFILE`, `HERMETIC_FS_ROOT`.
4. CLI flags.

### Security Considerations

* Python-level guards are preventative; they can be bypassed via native code, alternative interpreters, or undefined
  behavior. For hostile code, pair with OS isolation (containers, user namespaces + seccomp, Windows Sandbox).
* Blocking metadata endpoints reduces risk of credential discovery in cloud CI.
* Be explicit about **threat model**: default aims at “well-behaved but mistake-prone” code and most Python libraries,
  not advanced adversaries.

### Backwards Compatibility

* No changes to Python itself or `argparse`.
* Existing console scripts run unchanged; only the launch mechanism differs.

### Reference Implementation Sketch (normative behaviors)

```python
# split argv
split = sys.argv.index('--')  # ValueError => usage error
hermetic_argv = sys.argv[1:split]
target_argv = sys.argv[split + 1:]

# parse hermetic flags (argparse over hermetic_argv only)
ns = hermetic_parser.parse_args(hermetic_argv)

# decide mode
spec = target_argv[0]
module, callable_or_main, mode = resolve_target(spec)  # consult entry_points, or shebang

# install guards (or prepare sitecustomize dir for subprocess mode)
if mode == 'inprocess':
    install_guards(ns)
    sys.argv = target_argv  # pass-through argv for target
    invoke(module, callable_or_main)  # import after guards
else:
    site_dir = write_sitecustomize(ns)  # contains sitecustomize.py
    env = os.environ.copy()
    env['PYTHONPATH'] = site_dir + os.pathsep + env.get('PYTHONPATH', '')
    execve(target_executable, target_argv, env)  # same entry point, guarded
```

### Worked Examples

**Block network for HTTPie**

```
hermetic --no-network -- http https://example.com
# stderr: [hermetic] blocked socket.create_connection host=example.com reason=no-network
# exit code: 2
```

**Allow only localhost and deny subprocess**

```
hermetic --no-network --allow-localhost --no-subprocess -- devserver --port 8000
```

**Using pipx-installed tool**

```
# http is a pipx console script pointing to a different interpreter
hermetic --no-network -- http https://example.com
# hermetic detects foreign Python, injects sitecustomize, and execs the same script path
```

**Explicit module form**

```
hermetic --no-network -- httpie.__main__ -- https://example.com
```

### Guidance for Tool Authors (argparse interoperability)

* No changes required. Hermetic passes a clean `sys.argv` to the target exactly as given after `--`.
* If your CLI re-execs itself (rare), guards remain active in in-process mode; in subprocess bootstrap mode, ensure
  `PYTHONPATH` is preserved so `sitecustomize` stays on `sys.path`.

### Alternatives Considered

* **LD_PRELOAD / OS firewalls**: stronger isolation, but non-portable, needs admin rights, and doesn’t address
  Python-specific escape hatches uniformly.
* **pytest plugins**: tied to pytest lifecycle; not suitable for plain CLI runs.
* **AST rewriting**: invasive, brittle, and changes code provenance.

---

## Reference Profiles (non-normative)

* `net-hermetic` = `--no-network --allow-localhost`
* `exec-deny`    = `--no-subprocess`
* `fs-readonly`  = `--fs-readonly`
* `strict-imports` = `--strict-imports`

---

## Copyright

This document is placed in the public domain or under the CC0-1.0 license.

---

### Implementation Notes (for reviewers)

* Minimal PoC can be delivered in ~200 LOC with two modes (in-process + sitecustomize bootstrap), explicit `--` split,
  and the specified guard surfaces.
