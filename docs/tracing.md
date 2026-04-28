# Tracing and Debugging

When something gets blocked and you can't tell *what*, turn on
`--trace` (CLI) or `trace=True` (API). Hermetic prints one
structured line per blocked action to stderr.

## What you get

```text
[hermetic] blocked socket.connect host=example.com reason=no-network
[hermetic] blocked socket.getaddrinfo host=api.example.com reason=no-network
[hermetic] blocked socket.bind host=0.0.0.0 reason=no-network
[hermetic] blocked subprocess reason=no-subprocess
[hermetic] blocked open write path=/tmp/x
[hermetic] blocked open read-outside-root path=/etc/passwd
[hermetic] blocked fs mutation
[hermetic] blocked import name=ctypes
[hermetic] blocked native import spec=lxml._elementpath
```

Each line is one event. The format is human-readable but stable
enough to grep:

```text
[hermetic] blocked <api> [host=...|path=...|name=...] reason=<flag>
```

## Reading the output

The trace fires for **every** intercepted call, including ones
that were ultimately allowed through (you'll see the allowed
ones implicitly as success — only blocks are logged). If a target
makes a thousand DNS queries, you'll see a thousand lines.

When you see a blocked line, the next thing on stderr is usually
the resulting Python exception traceback. The two together tell
you both *what* hermetic blocked and *which call site* triggered
it.

```text
[hermetic] blocked socket.getaddrinfo host=example.com reason=no-network
hermetic: blocked action: network disabled: DNS(example.com)
```

If you ran via the CLI, that second `hermetic:` line is the only
output the user sees by default; the `[hermetic]` traces are
extra detail.

## Turning trace on

CLI:

```bash
hermetic --no-network --trace -- python my_script.py
```

API:

```python
from hermetic import hermetic_blocker

with hermetic_blocker(block_network=True, trace=True):
    ...
```

Trace is per-config, so an outer `hermetic_blocker` with
`trace=False` followed by an inner one with `trace=True` will
trace inner-block events only — except guards are global, so in
practice the merged config wins (trace ORs across nested
configs, like every other boolean).

## Secrets in trace output

Trace lines include hostnames and file paths but **not**
process arguments or environment variables. Concretely:

- `socket.connect host=...` — the host the calling code used
  (already known to whoever called).
- `subprocess` events — only `reason=no-subprocess`, **not** the
  argv. Argv is suppressed because it commonly contains
  credentials.
- `open path=...` — the path the calling code passed.
- `import name=...` — the module name.

If your `--allow-domain` list itself contains secret hostnames
(unusual but possible), trace will reveal which of them were
attempted. Don't enable trace if that's a concern.

## Inspecting blocks programmatically

`PolicyViolation` is a normal Python exception. Catch it to
inspect the message:

```python
from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation

with hermetic_blocker(block_network=True):
    try:
        import urllib.request
        urllib.request.urlopen("https://example.com")
    except PolicyViolation as exc:
        print(f"intercepted: {exc}")
        # intercepted: network disabled: DNS(example.com)
```

The exception message format mirrors the trace `reason` strings
but without the `[hermetic]` prefix.

## Common debugging questions

### "Nothing was blocked but I expected it to be."

Possibilities:

- The library captured a reference to the API before hermetic
  installed. (See [Threat Model](threat-model.md).) Try installing
  guards earlier — for the CLI this means making sure your tool
  is the resolved target, not a wrapper that imports hermetic
  late.
- The library is using a native extension that bypasses Python.
  Add `--block-native`.
- The library is running in a subprocess. Add `--no-subprocess`,
  or rely on the bootstrap to inject guards into the target's
  interpreter.

### "Something was blocked that I want to allow."

- Network: add `--allow-domain DOMAIN` for the host.
- Network localhost: add `--allow-localhost`.
- Filesystem: drop `--fs-readonly`, or set `--fs-readonly=ROOT`
  to widen the read root.
- Native imports: drop `--block-native` (there is no allow-list).

### "I want to see what the target imports."

Hermetic doesn't trace successful imports. Use
`PYTHONVERBOSE=1` or `python -v` for that — orthogonal tooling.

### "Bootstrap mode and trace together."

`--trace` works in bootstrap mode the same way: the bootstrap
sitecustomize honors the `trace` flag from `HERMETIC_FLAGS_JSON`
and writes the same `[hermetic] ...` lines to the target
interpreter's stderr.
