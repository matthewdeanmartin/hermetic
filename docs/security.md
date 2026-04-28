# Security

## Reporting a vulnerability

If you find a way to bypass hermetic's guards in a way that is **not
already documented** as a known limitation in
[`spec/secure_secure.md`](https://gitlab.com/matthewdeanmartin/hermetic/-/blob/main/spec/secure_secure.md)
or the [Threat Model](threat-model.md), please report it.

- **Preferred:** open a private security advisory on the GitLab
  project: <https://gitlab.com/matthewdeanmartin/hermetic>
- **Alternative:** email the maintainer (see PyPI metadata for the
  current address) with the subject prefix `[hermetic security]`.

For **already-documented** bypasses (captured references, native
code, `_socket.socket`, etc.), a public issue is fine — these are
not embargoed.

## Realistic scope

Before reporting, please read the [Threat Model](threat-model.md)
and skim `spec/secure_secure.md`. Hermetic is a userspace
sandbox; certain bypass classes are **out of scope by
construction**:

- Anything that requires the attacker not to have arbitrary
  Python code execution. Hermetic assumes they do.
- Anything that requires native code (`ctypes`, `.so`/`.pyd`).
  Use `--block-native` to mitigate; bypasses *with* `--block-native`
  on are in scope.
- Anything that requires walking `gc.get_objects()` to recover
  hidden state. Hermetic does not promise to defeat this.
- Bypasses unique to interpreters other than CPython. PyPy,
  Jython, GraalPy support is best-effort.

In scope:

- A way to exfiltrate data over the network with `--no-network`
  on, no native imports, and no captured-reference precondition.
- A write to the filesystem with `--fs-readonly` on through a
  Python-level API hermetic should reasonably patch.
- A subprocess invocation with `--no-subprocess` on through a
  Python-level API hermetic should reasonably patch.
- Information leakage in trace output (e.g. argv exposure that
  contains secrets).

## Disclosure timeline

Best-effort, given this is a single-maintainer project:

| Step | Target |
|---|---|
| Acknowledge receipt | 5 business days |
| Initial assessment | 14 days |
| Fix or documented mitigation | 60 days |
| Public disclosure / changelog entry | After fix released, or after 90 days if no fix is feasible |

For the "no fix is feasible" case, the limitation gets a paragraph
in `spec/secure_secure.md` with explicit guidance to pair hermetic
with a real sandbox if it matters to you.

## Supply chain

The `hermetic-seal` distribution has **zero runtime dependencies**.
Everything is implemented against the Python standard library. This
deliberately limits the supply-chain attack surface to:

- The Python interpreter you choose to run hermetic with.
- The hermetic source itself, hosted on GitLab and published to
  PyPI.

See [Dependency Provenance](dependency-provenance.md) for how
hermetic's own dependencies (build-time and dev-time) are managed.

## Cryptographic considerations

Hermetic does not perform cryptographic operations. The "always
deny" cloud metadata list and the suffix-match domain allow-list
are textual comparisons; there is no signature verification or
key material involved.

If you wrap a target that does crypto (e.g. `cryptography`,
`pyca`), be aware that `--block-native` will prevent loading the
relevant native extensions. In practice this means `cryptography`,
`bcrypt`, `pynacl`, etc. cannot be imported under `--block-native`.

## Reproducibility

- Hermetic is deterministic given the same flags and the same
  Python interpreter.
- The bootstrap-mode `sitecustomize.py` is generated from
  versioned source (`scripts/build_bootstrap.py`) and committed
  into the repo. Builds are reproducible from a tagged release.
