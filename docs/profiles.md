# Profiles

A **profile** is a named bundle of flags. Use one when you don't want
to spell out every guard, or when a team wants a shared baseline.

```bash
hermetic --profile net-hermetic -- my_app
```

Profiles **compose by union**. Passing `--profile A --profile B`
enables every flag set in either. Combining a profile with explicit
flags is allowed — explicit flags can only add to a profile, never
remove from it.

## Built-in profiles

### `block-all`

Lock down everything.

| Equivalent flags |
|---|
| `--no-network --no-subprocess --fs-readonly --block-native` |

Use when you want a target to fail fast at the first sign of any
side-effect.

### `net-hermetic`

Block network, but keep localhost reachable so test fixtures and
loopback servers still work.

| Equivalent flags |
|---|
| `--no-network --allow-localhost` |

The standard "no internet, but a local Postgres is fine" setup.

### `exec-deny`

Block subprocess invocation.

| Equivalent flags |
|---|
| `--no-subprocess` |

### `fs-readonly`

Make the filesystem read-only (writes denied; reads anywhere allowed).

| Equivalent flags |
|---|
| `--fs-readonly` |

### `block-native`

Refuse to load native extensions and FFI libraries.

| Equivalent flags |
|---|
| `--block-native` |

## Composition rules

When merging a profile into the current config, hermetic only ever
turns flags **on**:

- Boolean flags merge by `OR`. Once on, never off.
- List flags (e.g. `allow_domains`) merge by extension.
- String flags (e.g. `fs_root`) overwrite if the new value is
  truthy and the existing one is empty.

In other words: a later profile cannot undo an earlier one.

```bash
# All of network, subprocess, filesystem-write, and native imports blocked.
hermetic --profile block-all --profile net-hermetic -- my_app
# (net-hermetic adds --allow-localhost on top of block-all.)
```

## Custom profiles

There is no config-file mechanism for user-defined profiles yet.
For now, define a thin wrapper script:

```bash
#!/usr/bin/env bash
# my-hermetic
exec hermetic \
    --no-network \
    --allow-domain api.internal.com \
    --no-subprocess \
    --fs-readonly=./workspace \
    -- "$@"
```

Or build a config in Python and pass kwargs to `hermetic_blocker`:

```python
from hermetic import hermetic_blocker

DEFAULT_POLICY = dict(
    block_network=True,
    allow_domains=["api.internal.com"],
    block_subprocess=True,
    fs_readonly=True,
    fs_root="./workspace",
)

with hermetic_blocker(**DEFAULT_POLICY):
    ...
```

## Profile reference (for tool authors)

Profiles are defined in `hermetic/profiles.py` as a `dict[str, GuardConfig]`. The merge logic is:

```python
# pseudo-code
def apply_profile(base: GuardConfig, name: str) -> GuardConfig:
    prof = PROFILES[name]
    merged = copy(base)
    for k, v in prof.fields():
        if v is truthy:
            if bool: merged[k] = True
            if list: merged[k].extend(v)
            if str:  merged[k] = v
    return merged
```
