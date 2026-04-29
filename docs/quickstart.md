# Quick Start

A five-minute tour. Install `hermetic-seal`, then walk through the
examples below.

## 1. Block the network for a third-party CLI

```bash
hermetic --no-network -- http https://example.com
```

Output:

```text
hermetic: blocked action: network disabled: DNS(example.com)
```

`http` is the [HTTPie](https://httpie.io/) console script. It tried to
resolve `example.com`, hermetic intercepted `socket.getaddrinfo`, and the
process exited with code `2` (the standard "blocked action" exit code).

The `--` is **mandatory**. Everything before `--` is parsed by hermetic;
everything after is forwarded verbatim to the target.

## 2. Block the network for your own code

```python
from hermetic import with_hermetic

@with_hermetic(block_network=True)
def fetch():
    import requests
    return requests.get("https://example.com")

fetch()  # raises hermetic.PolicyViolation
```

The decorator installs guards before your function runs and removes
them after (regardless of exception).

## 3. Allow some hosts but not others

```bash
hermetic --no-network --allow-domain api.internal.com -- my_app
```

`--allow-domain` is repeatable. Matches are **suffix-based** —
`api.internal.com` allows `api.internal.com` and `*.api.internal.com`,
but not `api.internal.com.attacker.example`.

Cloud metadata endpoints (`169.254.169.254`,
`metadata.google.internal`, IPv6 metadata variants) are **always
blocked** — `--allow-domain` cannot allow them.

## 4. Make the filesystem read-only

```bash
hermetic --fs-readonly=./sandbox -- python my_script.py
```

`my_script.py` may read files **inside `./sandbox`** and may not write
anywhere. Reads outside the root and any kind of write raise
`PolicyViolation`.

If you omit the `=PATH`, all reads are still allowed; only writes are
denied.

## 5. Lock everything down at once

```bash
hermetic --profile block-all -- my_analyzer.py --input data.csv
```

The `block-all` [profile](profiles.md) bundles `--no-network --no-subprocess --fs-readonly --no-environment --no-code-exec --no-interpreter-mutation --block-native`. Use it when you have
no idea what your target wants and you want to find out the loud way.

## 6. Use the context manager

```python
from hermetic import hermetic_blocker
import os

# Subprocesses allowed here.
os.system("echo allowed")

with hermetic_blocker(block_subprocess=True):
    # Inside this block, os.system raises PolicyViolation.
    os.system("echo blocked")  # PolicyViolation
```

The context manager nests safely — see [Programmatic API](programmatic-api.md).

## 7. See what got blocked

Add `--trace` (CLI) or `trace=True` (API) to print every blocked call
to stderr:

```bash
hermetic --no-network --trace -- python -c "import urllib.request; urllib.request.urlopen('https://x')"
```

```text
[hermetic] blocked socket.getaddrinfo host=x reason=no-network
hermetic: blocked action: network disabled: DNS(x)
```

## Where to go next

- [CLI Usage](cli-usage.md) — every flag in detail.
- [Programmatic API](programmatic-api.md) — context manager, decorator, nesting.
- [Profiles](profiles.md) — named bundles of flags.
- [Threat Model](threat-model.md) — what hermetic actually defeats.
