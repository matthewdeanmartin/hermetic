# Threat Model

Hermetic is a **userspace, in-process Python sandbox**. It is not a
security boundary. This page exists so you can decide whether
hermetic fits your problem before you depend on it.

## What hermetic is good for

- **Yourself.** Guaranteeing that a unit test really is hermetic —
  even on a developer laptop where the API is offline anyway, even
  in CI where the network policy might be looser than you assume.
  The test fails loudly when something tries to phone home.
- **Poorly-behaved-but-not-malicious plugins.** A library you
  depend on that decides to fetch a remote schema, or write
  `.cache/` into `$HOME`, or shell out to `git` when you didn't ask
  it to. Hermetic catches these and tells you which API the library
  reached for.
- **Poorly-behaved-but-not-malicious LLMs.** The agent you handed a
  Python interpreter that decides "I'll just `pip install` that
  real quick" or fetches a URL outside its allow-list.
- **Defense in depth** alongside a real sandbox (container,
  `seccomp`, `gVisor`). Hermetic catches policy violations earlier
  and with better error messages than the kernel, which makes
  debugging much faster.

## What hermetic is *not* good for

- **A determined attacker** with arbitrary Python code execution
  inside your interpreter. They can bypass hermetic. See "known
  bypass classes" below.
- **Sandboxing untrusted user input.** If you're tempted to use
  hermetic to safely `eval()` user-supplied Python, **don't**. Use
  a real sandbox.
- **Running known-malicious code.** Anything written specifically
  to defeat hermetic will defeat it. The escape hatches are well
  understood and documented.

## Assumed attacker capabilities

Inside the same interpreter, hermetic assumes the attacker can:

- Call any Python API.
- Read process memory by ordinary Python means
  (`gc.get_objects()`, `inspect`, `__dict__` walking).
- Import any installed module.
- Write files anywhere `--fs-readonly` doesn't cover.

Hermetic assumes the attacker **cannot**:

- Produce machine code from scratch.
- Escape Python's bytecode VM via memory corruption.
- Modify the interpreter binary on disk.

If your attacker has the second or third capability, no userspace
guard helps anyway.

## Known bypass classes

Honest enumeration of what hermetic does not stop. Most are
mitigated to some degree but not eliminated.

### Native code / FFI

- **Direct `ctypes` calls** — fully mitigated only when
  `--block-native` is on. Without it, ten lines of `ctypes` reach
  `system(3)` directly.
- **Already-loaded native extensions** — once a `.so` / `.pyd` is
  in memory, hermetic can't evict it. `--block-native` prevents
  *new* native loads.
- **`_ctypes` private internals** — partially patched but not
  exhaustive. Determined code can rebuild `CDLL` from
  `_ctypes._SimpleCData` plus `_FuncPtr`.

### Captured references

- Any module that did `from socket import socket` (or `from
  subprocess import Popen`, etc.) **before hermetic installed**
  holds the original callable in its dict. Hermetic's
  monkey-patches replace the *attribute on the source module*,
  not every existing reference. `urllib3` keeps an internal pool
  of socket references. `requests` doesn't.
- Mitigation: hermetic should be installed as early as possible
  in the process. The CLI runner installs guards *before*
  importing the target. The bootstrap-mode `sitecustomize` runs
  before any user code.

### Patch removal

- `hermetic.guards.uninstall_all()` is publicly importable.
  Attacker code can call it, restoring the originals from
  hermetic's own module globals.
- Mitigation: `--seal` / `sealed=True`. Once sealed, the
  uninstall path is a no-op for the rest of the process. Not
  bulletproof — a determined attacker can still walk
  `gc.get_objects()` to find the originals — but it raises the
  bar from one line to many. See [Sealed Mode](sealed-mode.md).

### Network: residual surface

- **`_socket.socket` direct construction** — the C-level base
  class isn't patched. (Patching it causes infinite recursion in
  `socket.socket.__init__`.) An attacker who knows this gets a
  raw socket, but still has to do their own DNS, which `--no-network`
  blocks via `getaddrinfo`.
- **DNS-over-HTTPS through an allow-listed domain** — out of
  scope. If you allow a CDN that fronts a public DoH resolver,
  any host is reachable by name.
- **Bind for inbound exfil** — partially mitigated; binds to
  non-loopback interfaces are denied when `--no-network` is on.

### Subprocess: residual surface

- **Captured `subprocess.Popen` references** — same class as the
  socket case.
- **Windows `CreateProcess` at the C level** — high-level
  `subprocess`, `os.system`, and `os.spawn*` are patched, but a
  custom C extension that calls `CreateProcessW` directly bypasses.
  `--block-native` mitigates by preventing such an extension from
  loading.
- **`pty.fork`** — patched. `os.fork` — patched. `os.forkpty` —
  patched. `posix.fork` (the C-level alias) — not patched
  separately; `os.fork` patching covers most callers.

### Filesystem: residual surface

- **Symlink TOCTOU** — between `realpath` and `open`, an attacker
  with write access could swap a symlink. Not mitigated.
- **`scandir`/`listdir` outside the root** — the *open path* is
  constrained, but directory listings may reveal the existence
  of out-of-root files. Their *contents* are still protected.

## Defense-in-depth recipe

If you have an actual untrusted-code problem, layer:

1. **OS sandbox** (container, `gVisor`, Windows Sandbox, AppArmor,
   `seccomp`). This is the actual security boundary.
2. **Hermetic with `--seal`** inside the sandbox. Loud failures,
   readable error messages, fast feedback.
3. **A capability-passing protocol** at the interface — give the
   tool what it needs, not access to what it might need.

If you have an "accidental side-effects" problem, hermetic alone is
fine.

## Reading further

- `spec/secure_secure.md` in the repo — full security review and
  hardening plan, with a phased roadmap.
- `exploits/` directory — concrete bypass demonstrations.
- [Security](security.md) page — reporting and disclosure policy.
- [Sealed Mode](sealed-mode.md) — opt-in irreversible install.
