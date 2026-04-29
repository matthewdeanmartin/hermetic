# API Reference

Auto-generated from docstrings via
[`mkdocstrings`](https://mkdocstrings.github.io/). For prose
explanations of the same APIs, see [Programmatic
API](programmatic-api.md).

## Public API (`hermetic`)

The top-level package re-exports the two intended entry points:

```python
from hermetic import hermetic_blocker, with_hermetic
```

::: hermetic
options:
members:
\- hermetic_blocker
\- with_hermetic
\- __version__

## Blocker (`hermetic.blocker`)

::: hermetic.blocker
options:
members:
\- hermetic_blocker
\- with_hermetic
\- BlockConfig

## Errors (`hermetic.errors`)

::: hermetic.errors

## Profiles (`hermetic.profiles`)

::: hermetic.profiles
options:
members:
\- GuardConfig
\- PROFILES
\- apply_profile

## CLI (`hermetic.cli`)

::: hermetic.cli
options:
members:
\- main
\- build_parser
\- parse_hermetic_args

## Runner (`hermetic.runner`)

::: hermetic.runner
options:
members:
\- run
\- config_to_flags

## Resolver (`hermetic.resolver`)

::: hermetic.resolver
options:
members:
\- TargetSpec
\- resolve
\- invoke_inprocess

## Bootstrap (`hermetic.bootstrap`)

::: hermetic.bootstrap
options:
members:
\- write_sitecustomize

## Guards

These submodules implement the actual monkey-patches. They are
public for advanced users who want to install one guard at a time
without going through `hermetic_blocker`, but most callers should
use the public API above.

### `hermetic.guards`

::: hermetic.guards
options:
members:
\- install_all
\- uninstall_all

### `hermetic.guards.network`

::: hermetic.guards.network
options:
members:
\- install
\- uninstall

### `hermetic.guards.subprocess_guard`

::: hermetic.guards.subprocess_guard
options:
members:
\- install
\- uninstall

### `hermetic.guards.filesystem`

::: hermetic.guards.filesystem
options:
members:
\- install
\- uninstall

### `hermetic.guards.imports_guard`

::: hermetic.guards.imports_guard
options:
members:
\- install
\- uninstall
