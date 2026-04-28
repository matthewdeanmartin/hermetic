# Sealed Mode

By default, hermetic guards are reversible — `uninstall_all()`
restores the originals. That's the right behavior for tests and
ad-hoc scripts: you wouldn't want a `pytest` fixture to
permanently break socket access for the rest of the session.

For everything else, **sealed mode** turns guard installation into
a one-way door.

## What sealed mode does

When you pass `--seal` (CLI) or `sealed=True` (API):

- The first call to `install_all()` activates a process-wide
  `_SEALED` latch.
- Subsequent calls to `uninstall_all()` are **no-ops**. Guards are
  never removed.
- `_HermeticBlocker.__exit__` still runs reference counting, but
  the eventual uninstall step is suppressed.
- Nested `hermetic_blocker` blocks may still **widen** the policy
  (add more guards) — they cannot weaken it.

## What sealed mode does *not* do

- It does not hide hermetic's `_originals` dicts. An attacker who
  knows where to look can still find them in
  `sys.modules['hermetic.guards.network']._originals` and reapply
  them by hand.
- It does not prevent direct module attribute writes. Code that
  does `socket.socket = original` from outside hermetic still
  works (hermetic doesn't install a `__setattr__` veto on the
  module).
- It does not survive interpreter restart. A fresh process starts
  unsealed.

In short, sealed mode raises the bar from "one line of code
removes the guards" to "an attacker has to know the structure of
hermetic's internals". Useful against careless code and mildly
mischievous LLMs; not useful against a determined adversary.

## When to use it

- **LLM tool runners.** The model has access to a Python
  interpreter and you want it to fail loudly if it tries
  `hermetic.guards.uninstall_all()`.
- **Long-lived sandboxed processes.** A worker that should
  enforce a single policy for its whole lifetime.
- **CI guardrails** where the policy should not be re-negotiable
  by the test code itself.

When **not** to use it:

- Inside a pytest run with multiple tests that need different
  policies. Once one test seals, all subsequent tests are stuck
  with that policy.
- Inside a REPL or notebook where you want to experiment with
  flag combinations.
- Inside library code that other people will call. Sealing on
  import is an antisocial choice.

## Examples

CLI:

```bash
hermetic --seal --no-network --no-subprocess --block-native \
    -- python long_running_worker.py
```

Programmatic:

```python
from hermetic import hermetic_blocker

with hermetic_blocker(
    block_network=True,
    block_subprocess=True,
    block_native=True,
    sealed=True,
):
    # Guards stay on for the rest of the process — even after this
    # block exits.
    run_forever()
```

Decorator:

```python
from hermetic import with_hermetic

@with_hermetic(block_network=True, sealed=True)
def main():
    ...

main()
# Network is still blocked here; cannot be re-enabled.
```

## Combining sealed with the bootstrap

In bootstrap mode, sealed mode applies to the **target's**
interpreter. The target's process can no longer remove the
guards even by importing `hermetic` and calling `uninstall_all()`.

The hermetic launcher process is short-lived (it `execve`s into
the target on POSIX, or spawns and waits on Windows), so sealing
only matters for the target.
