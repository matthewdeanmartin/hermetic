# Programmatic API

Use hermetic from inside Python without going through the CLI. Two
forms — a context manager and a decorator — both backed by the same
implementation in `hermetic.blocker`.

## `hermetic_blocker(...)`

A reentrant, thread-safe context manager that installs guards on
entry and removes them on exit (unless `sealed=True`).

```python
from hermetic import hermetic_blocker

with hermetic_blocker(block_network=True, block_subprocess=True):
    ...
```

It is also a decorator (it inherits from `contextlib.ContextDecorator`):

```python
@hermetic_blocker(block_network=True)
def main():
    ...
```

And it works in async contexts:

```python
async with hermetic_blocker(block_network=True):
    ...
```

### Keyword arguments

All arguments are keyword-only.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `block_network` | `bool` | `False` | Same as `--no-network`. |
| `block_subprocess` | `bool` | `False` | Same as `--no-subprocess`. |
| `fs_readonly` | `bool` | `False` | Same as `--fs-readonly`. |
| `fs_root` | `str \| None` | `None` | Same as `--fs-readonly=ROOT`; requires `fs_readonly=True`. |
| `block_environment` | `bool` | `False` | Same as `--no-environment`. |
| `block_code_exec` | `bool` | `False` | Same as `--no-code-exec`. |
| `block_interpreter_mutation` | `bool` | `False` | Same as `--no-interpreter-mutation`. |
| `block_native` | `bool` | `False` | Same as `--block-native`. |
| `allow_localhost` | `bool` | `False` | Same as `--allow-localhost`. |
| `allow_domains` | `Iterable[str]` | `()` | Same as repeated `--allow-domain`. |
| `deny_imports` | `Iterable[str]` | `()` | Same as repeated `--deny-import`. |
| `trace` | `bool` | `False` | Same as `--trace`. |
| `sealed` | `bool` | `False` | Same as `--seal`. See [Sealed Mode](sealed-mode.md). |

## `with_hermetic(...)`

A decorator factory with the same kwargs as `hermetic_blocker`.
It is a thin alias kept for readability:

```python
from hermetic import with_hermetic

@with_hermetic(block_network=True, allow_domains=["api.internal.com"])
def process_data():
    import requests
    # Blocked: not on the allow-list.
    # requests.get("https://example.com")

    # Allowed.
    return requests.get("https://api.internal.com/data")
```

## Nesting and reentrancy

Guards are global monkey-patches — they affect the whole interpreter,
including all threads. `hermetic_blocker` is reference-counted:
nested entries combine their policies (the **union** wins, never the
intersection), and guards are removed only when the outermost
context exits.

```python
from hermetic import hermetic_blocker

with hermetic_blocker(block_network=True):
    # Network blocked.
    with hermetic_blocker(block_subprocess=True):
        # Network AND subprocess blocked.
        ...
    # Back to network blocked only.
# All guards removed.
```

This means an inner block **cannot weaken** an outer block. You
cannot `with hermetic_blocker(...): ...` your way back to a
permissive policy.

## Catching policy violations

When a guard blocks an action, it raises `hermetic.PolicyViolation`
(a subclass of `RuntimeError`). You can catch it like any other
exception:

```python
from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation

with hermetic_blocker(block_subprocess=True):
    try:
        import os
        os.system("echo hi")
    except PolicyViolation as e:
        print(f"blocked: {e}")
```

If you don't catch it, the exception propagates normally. The CLI
runner catches it at the top level and exits with code `2`.

## Threading caveats

Because guards patch global state, all threads in the interpreter
see the same policy. If thread A is inside `hermetic_blocker(...)`
and thread B is making a network call, thread B will hit the guard
too.

This is rarely a problem in practice — most uses of hermetic are
single-threaded scripts, single-threaded tests, or async event
loops. But be aware: there is no per-thread or per-coroutine
sandbox.

## Async usage

`hermetic_blocker` implements both the sync and async context
manager protocols. The async variants delegate to the sync ones —
guard installation is fast and synchronous, so there's nothing to
await.

```python
import asyncio
from hermetic import hermetic_blocker

async def main():
    async with hermetic_blocker(block_network=True):
        # asyncio.create_subprocess_* is also blocked when
        # block_subprocess=True.
        ...

asyncio.run(main())
```

## Examples

A pytest fixture that blocks network for one test:

```python
import pytest
from hermetic import hermetic_blocker

@pytest.fixture
def no_network():
    with hermetic_blocker(block_network=True, allow_localhost=True):
        yield

def test_offline_path(no_network):
    # Anything that hits the network in here will raise PolicyViolation.
    ...
```

A guarded entry point for an LLM tool runner:

```python
from hermetic import with_hermetic

@with_hermetic(
    block_network=True,
    allow_domains=["api.openai.com", "api.anthropic.com"],
    block_subprocess=True,
    fs_readonly=True,
    fs_root="/tmp/agent-workspace",
    block_environment=True,
    block_code_exec=True,
    block_interpreter_mutation=True,
    deny_imports=["pickle", "marshal"],
    block_native=True,
    trace=True,
)
def run_agent_tool(tool_call):
    return tool_call()
```
