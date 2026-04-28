# Hermetic — Security Review and Hardening Plan

> Scope: this is a **userspace, in-process Python sandbox**. The threat
> model from the README is honest: this is "envelope vs postcard" security,
> intended to defeat **opportunistic** misuse and accidental side effects
> (especially in unit tests and short-lived LLM tool calls), **not** a
> determined adversary with arbitrary code execution.
>
> Real isolation is `seccomp`, Landlock, `pledge(2)`, a container, a VM,
> or `gVisor`. Hermetic does not replace those.
>
> Goal of this document: enumerate concrete bypass classes against the
> current implementation, then ship a phased set of mitigations that
> close as many as practical without breaking the "drop into existing
> Python code, keep using requests/open()" usability story.

## 1. Threat model

We assume the attacker is **untrusted Python code** running in the same
interpreter as hermetic — e.g. an LLM-authored tool, a third-party
package, a fixture in someone else's test. The attacker can:

* call any Python API
* read process memory by ordinary Python means (`gc`, `inspect`, `__dict__`)
* import any installed module
* write files (unless `--fs-readonly`)

The attacker **cannot** (assumption): produce machine code from scratch,
escape Python's bytecode VM via memory corruption, or modify the
interpreter binary on disk. (If they can do the second one, no userspace
guard helps anyway.)

LLM-sandboxing scenario specifically: attacker is plausibly a confused
or mildly mischievous LLM, not a targeted attacker. We want it to be
*hard to bypass by accident*, and we want bypass attempts to be loud
(visible in trace) rather than silent.

## 2. Attack surface as it exists today

Concrete bypasses (some demoed in `exploits/a.py`):

### 2.1 Native code / FFI

* **`ctypes` direct C `system` call** (the `exploits/a.py` proof). Bypassed only when `--block-native` is on, and even then the import guard only filters `ctypes` and `cffi` by *name* — `_ctypes`, `ctypes.util`, `ctypes._SimpleCData`, etc. are not in `_DENY_NAMES`.
* **Already-imported `ctypes`**. If something else imported `ctypes` before `install()` ran, the *module* is in `sys.modules`. We patch `CDLL/PyDLL/...` on it, but we do **not** patch `_ctypes._SimpleCData`/`_FuncPtr`, and we do **not** invalidate cached references already obtained (`from ctypes import CDLL` then later `_ctypes` attribute access).
* **`ctypes.util.find_library`** is not blocked separately, but with `CDLL` neutralised it's mostly harmless. Still worth blocking for noise.
* **`cffi`** name-blocked; loaded-module patch only handles `cffi.FFI`. `cffi.api`, `cffi.dlopen`, etc. unhandled.
* **Native extension modules already on disk**. We subclass `ExtensionFileLoader.create_module`, but Python's import machinery uses `_bootstrap_external._NamespacePath` and `BuiltinImporter` for builtins. Our subclass replaces the **class** `mach.ExtensionFileLoader`, but existing `FileFinder` instances in `sys.path_hooks` were built with the original class — newly-imported native modules may still resolve via the cached path-finder using the original loader.

### 2.2 Subprocess

* **Subprocess-replacement libraries**: `sh`, `pexpect`, `plumbum`, `sarge`, `delegator`, `invoke`, `fabric` — all eventually call `subprocess.Popen`. Since we patch `subprocess.Popen` *the attribute on the module*, anything that did `from subprocess import Popen` *before* our install captured the original.
* **`_posixsubprocess.fork_exec`** — the real underlying primitive on POSIX. We do **not** patch it. Anyone re-creating `Popen` from scratch reaches it.
* **`posix.spawn` / `os.posix_spawn` / `os.posix_spawnp`** — not in our `os` deny list.
* **`multiprocessing`** — `multiprocessing.Process.start` ultimately calls `_posixsubprocess.fork_exec` or `CreateProcess`. Not patched.
* **`pty.fork`, `os.openpty`** — fork primitives we don't cover.
* **`os.fork` is patched but `os.forkpty` is patched too — fine. `posix.fork` (the C-level alias of `os.fork` on Linux) is the same function object so patching either suffices, *but* the attribute lives in two modules, so re-importing `posix` fetches the unpatched callable from `posixmodule`. We only patch `os`.**

### 2.3 Network

* **Already-imported `socket.socket`** captured by reference (`from socket import socket`) is the *original* class. Many real packages do this.
* **`_socket.socket`** — the C-level base class is unpatched. `_socket.socket(...)` returns a raw socket that bypasses our `GuardedSocket` class.
* **`socket.socketpair()`** — not patched (used to create a connected pair locally, and for some tunneling tricks).
* **`socket.fromfd()`** — not patched. With this and a leaked fd, the attacker reattaches to a kernel socket.
* **IPv6 metadata** (e.g. `fe80::a9fe:a9fe`, `[fd00:ec2::254]` on AWS IMDSv2 IPv6) not in `_METADATA_HOSTS`. The current set is two strings.
* **DNS-over-HTTPS / DoH** is just HTTP — if any allow_domain points at a CDN, it's a tunnel. Out of scope to fix.
* **Bind/listen** — we only block outbound. An attacker could bind a port and exfiltrate via someone else connecting in. Lower priority but real.
* **`urllib3` keeps an internal pool** that may have created a `socket.socket` *class reference* at import time. Same captured-reference problem.

### 2.4 Filesystem

* **`os.open` is patched**, but the C-level `posix.open` may be reachable (similar to `posix.fork`).
* **`io.open`** — alias of `builtins.open` in CPython at import time, but third-party libs sometimes import via `io.open`. We don't patch `io.open`.
* **`shutil.rmtree`, `shutil.copy*`, `shutil.move`** — these don't ultimately hit anything we *can't* block (they go through `os.unlink/rename/...`), **but** they capture references at import time. `shutil.rmtree` looks up `os.unlink` at call time so patching `os.unlink` works — verified by reading shutil. Still worth a defense-in-depth direct patch.
* **Symlink-via-readonly-root**: if the root is `./sandbox`, an attacker who can pre-stage a symlink inside it pointing outside it will read whatever it points to. We use `os.path.realpath` which resolves symlinks — good — but we only check the *open* path, not subsequent `os.scandir`/`os.listdir` results.
* **Mode-string parsing**: `open(p, "rb")` is correctly read-only. But `open(p, "r+b")` is write — we already detect `+`. `open(p, mode=0)` (a numeric mode for `os.open`) is not relevant since we treat the mode as a string. OK.
* **Path-typed values**: `pathlib.PurePath` instances stringify via `__fspath__`; `str(file)` may not call `__fspath__`. We should use `os.fspath()` for mode-aware checks.

### 2.5 Patch removal / state corruption

* `uninstall_all()` is publicly importable — attacker code can just call it. Even if we hide it, the originals are stored in module globals (`_originals`) reachable via `sys.modules['hermetic.guards.network']._originals`.
* `socket.socket = original` from the attacker side restores in one line.
* We have no "sealed" mode.

### 2.6 Bootstrap channel

* The bootstrap path writes a `sitecustomize.py` to a tempdir and prepends it to `PYTHONPATH`. The flags travel via env var `HERMETIC_FLAGS_JSON`. The attacker can read/modify env. We `pop()` the var inside the bootstrap, so a child can't inherit the flags — but the child *also* therefore won't be sandboxed (unless re-injected).
* The tempdir is left on disk (no cleanup).
* On Windows we spawn via `subprocess.run` after `install_all()` is *not* called in bootstrap mode — we pass through. That's correct (the child gets the `sitecustomize`), but it does mean a path-confusion attack between hermetic's process and the child's process must be considered.

## 3. Mitigation phases

Each phase is independently shippable. Tests + docs accompany each.

### Phase 1 — Native / import hardening (highest leverage; this is the demo bypass)

1. Expand `_DENY_NAMES` to include: `_ctypes`, `_cffi_backend`, `cffi`, `ctypes`, plus subprocess-replacement libs (`sh`, `pexpect`, `plumbum`, `sarge`, `delegator`) when `block_subprocess` is on.
2. Patch additional `ctypes` attributes when the module is already loaded: `LibraryLoader`, `util.find_library`, `_dlopen` if present.
3. Re-blacklist the `cffi` API surface more thoroughly: `dlopen`, `verify`, `set_source` on any imported submodule.
4. Invalidate `importlib.machinery.FileFinder` path-importer cache so future native imports go through our subclassed loader: walk `sys.path_importer_cache` and invalidate.
5. Wire the subprocess-replacement deny only when `block_subprocess=True` (don't punish unit-test users who only want network blocking).

### Phase 2 — Network bypass closure

1. ~~Patch `_socket.socket`~~ — *Tried, reverted*. `socket.socket` inherits from `_socket.socket`, so reassigning the base class causes infinite recursion in `socket.socket.__init__`. We accept the residual bypass (`_socket.socket(...)` direct instantiation) and rely on the patched DNS/connect surface to make it useless without DNS.
2. Patch `socket.socketpair`, `socket.fromfd`, `socket.fromshare`.
3. Add IPv6 metadata addresses to `_METADATA_HOSTS`: `fd00:ec2::254`, `fe80::a9fe:a9fe`.
4. Block `socket.socket.bind` to non-loopback when `allow_localhost` is False (so attackers can't open a listener for inbound exfil).
5. Don't try to fix DoH — document it.

### Phase 3 — Subprocess bypass closure

1. Patch `_posixsubprocess.fork_exec` to raise.
2. Patch `os.posix_spawn`, `os.posix_spawnp`.
3. Patch `multiprocessing.context.DefaultContext.Process` (or simpler: `multiprocessing.Process.start`) to raise.
4. Patch `pty.fork` (already implicit via `os.forkpty`, but explicit is clearer).
5. Patch `posix.fork` / `nt.CreateProcess` where reachable (best-effort).

### Phase 4 — Filesystem hardening

1. Patch `io.open` to alias the guarded `open`.
2. Patch `shutil.rmtree`, `shutil.move`, `shutil.copyfile`, `shutil.copytree` directly — they're documented entry points.
3. Use `os.fspath()` to coerce path-likes before mode-string checks.
4. Resolve symlinks before checking root containment for `os.scandir`, `os.listdir`, `os.readlink` (best-effort — these are reads, so only constrained if `fs_root` set).
5. Patch `os.replace`, `os.rename` to additionally verify *both* src and dst lie under the root (currently just denies all, which is correct under read-only — keep it that way).

### Phase 5 — Anti-uninstall (sealed mode)

1. Add a `sealed=True` (default `False` for backwards compat) option to `hermetic_blocker` and a `--seal` CLI flag. When sealed:
    * `uninstall_all()` becomes a no-op unless called with a process-local secret token generated at install time.
    * The originals dict is replaced with a closure that doesn't expose a `_originals` global on the module.
    * Best-effort: `socket.socket = something` triggers a `PolicyViolation` because we install a module `__setattr__` via a `ModuleType` wrapper or by replacing `socket.__class__` with a guarded subclass that vetoes attribute writes.
2. Document that this is not bulletproof — a determined attacker can still walk `gc.get_objects()` or `sys._current_frames()` to find originals — but it raises the bar above one-line bypasses.

### Phase 6 — Tests for the above + a "known-bypass" test catalogue

* Add a `test/test_security/` directory whose tests assert that the listed bypasses are blocked (when guards are on) and *succeed* (when guards are off). The latter is important: it prevents us from claiming we block something that the host Python doesn't actually permit anyway.
* Bring the `exploits/a.py` style demo into a parametric test.

### Phase 7+ (future, out of scope here)

* Resource limits via `resource.setrlimit` on POSIX (already in TODO.md).
* Audit-hook integration (`sys.addaudithook`) — much stronger than monkey-patching; CPython 3.8+. We could rewrite the whole guard layer atop audit hooks. Out of scope for this pass but flagged as the long-term direction.
* SELinux/AppArmor profiles for the bootstrap interpreter — system-admin task.

## 4. What we're explicitly NOT going to do

* Try to win against an adversary with arbitrary code execution. The README is honest; we shouldn't oversell this.
* Add cryptographic signing of the originals (it doesn't help — attacker reads memory).
* Patch every C function in CPython. Whack-a-mole.

## 5. Compatibility / usability principle

If a mitigation breaks the common case ("I just want my unit test to not hit the network"), it's wrong. Specifically:

* `requests`, `urllib`, `httpx`, `aiohttp` must keep working when the guard is off.
* `subprocess.run("ls")` must keep working when only `--no-network` is set.
* Sealed mode is opt-in.

Where a mitigation can't help (e.g. captured-reference bypass), we document it rather than break the common path.
