# hermetic-seal

> A best-efforts, user-space sandbox for Python.

`hermetic` runs a Python tool — your script, somebody else's CLI, a unit test —
with selected APIs disabled. Block outbound network. Block subprocess. Make the
filesystem read-only. Refuse to load native extensions.

It is **not** a security boundary against a determined attacker. It is a
defense against:

- **Yourself** — guarantee a unit test really is hermetic, not just "hermetic
  on this developer's laptop where the API is offline anyway".
- **Poorly-behaved-but-not-malicious plugins** — the third-party library that
  phones home, writes a `.cache/` directory in `$HOME`, or shells out to `git`
  when you didn't ask it to.
- **Poorly-behaved-but-not-malicious LLMs** — the agent that, given access to
  your interpreter, decides "I'll just `pip install` that real quick" or
  fetches a URL it shouldn't.

## What it isn't

If [Alice and Bob](https://en.wikipedia.org/wiki/Alice_and_Bob) know about
your application and are specifically targeting it, this tool won't help.
This is "envelope instead of postcard" security. This is "lock your front
door with a standard key that can be picked with a $5 purchase on eBay"
security.

For real isolation, use a container, a VM, `seccomp`, Landlock, or
`gVisor`. See the [Threat Model](threat-model.md) page for an honest
account of what hermetic does and does not defend against.

## Two ways to use it

**As a CLI wrapper** around any Python console script:

```bash
hermetic --no-network -- http https://example.com
# hermetic: blocked action: network disabled: DNS(example.com)
```

**As a library** inside your own code:

```python
from hermetic import with_hermetic

@with_hermetic(block_network=True, allow_localhost=True)
def main():
    ...
```

## Where to go next

- [Installation](installation.md) — install via pip, uv, or pipx.
- [Quick Start](quickstart.md) — five-minute tour.
- [CLI Usage](cli-usage.md) — every flag explained.
- [Programmatic API](programmatic-api.md) — context manager and decorator.
- [Threat Model](threat-model.md) — what this defeats and what it doesn't.
- [API Reference](api-reference.md) — generated from docstrings.
