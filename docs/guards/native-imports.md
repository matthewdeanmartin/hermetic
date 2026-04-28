# Native Imports Guard

Activated by `--block-native` (CLI) or `block_native=True` (API).
Implemented in `hermetic/guards/imports_guard.py`.

## Why a guard for native imports?

If you block network and subprocess at the Python level but allow
native code interop, the bypass is trivial: a few lines of `ctypes`
calling `system(3)` or `connect(2)` skips every Python guard in
hermetic. (See `exploits/a.py` in the repo for a worked example.)

`--block-native` raises the bar by:

1. Refusing to import the FFI modules (`ctypes`, `_ctypes`, `cffi`,
   `_cffi_backend`).
2. Replacing `importlib.machinery.ExtensionFileLoader` with a
   subclass that refuses to load `.so` / `.pyd` extensions.
3. Patching the dangerous attributes on already-loaded `ctypes` /
   `cffi` modules to raise `PolicyViolation` when called.

## What it patches

### Import-time denial

The top-level package import is blocked for:

| Always | When `--no-subprocess` is also on |
|---|---|
| `ctypes` | `sh` |
| `_ctypes` | `pexpect` |
| `cffi` | `plumbum` |
| `_cffi_backend` | `sarge` |
| | `delegator` |

The right-hand list is for subprocess-replacement libraries that
capture `subprocess` references at import time, making them harder
to patch after the fact.

### Native extension loader

`importlib.machinery.ExtensionFileLoader` is replaced with a
subclass whose `create_module` raises `PolicyViolation`. Importer
caches are invalidated so the new class is consulted for any
subsequent import.

### Already-loaded `ctypes` / `cffi`

If `ctypes` or `cffi` was imported *before* hermetic installed
(very common — many libraries pull them in transitively), the
top-level import block doesn't help. Hermetic also patches the
following attributes on the loaded modules:

| Module | Attributes patched |
|---|---|
| `ctypes` | `CDLL`, `PyDLL`, `WinDLL`, `OleDLL`, `LibraryLoader`, `cdll`, `pydll`, `windll`, `oledll` |
| `ctypes.util` | `find_library`, `find_msvcrt` |
| `cffi` | `FFI`, `dlopen`, `verify` |

Each is replaced with a callable that raises `PolicyViolation`.

## What it does *not* catch

- **Already-loaded native extension modules**. `numpy`, `lxml`,
  `cryptography`, etc. — if they're already imported when hermetic
  runs, their C code is in memory and reachable via Python. Hermetic
  cannot evict them.
- **Captured references**. `from ctypes import CDLL` before
  hermetic installs gives the caller the unpatched class. Same
  class of bypass as the other guards.
- **`_ctypes` private internals**. Some internal types
  (`_ctypes._SimpleCData`, `_FuncPtr`) are not in the deny list.
  An attacker who knows them can build a `CDLL`-equivalent. The
  spec/secure_secure.md document tracks this as a known
  partially-mitigated bypass.
- **Cached `FileFinder` instances on `sys.path_hooks`**. We
  invalidate the importer cache, but a `FileFinder` constructed
  before our subclass install holds the original `ExtensionFileLoader`
  class in its loaders tuple. Newly-imported native modules go
  through the new path; modules whose finders were already cached
  may not.

## Tracing

```text
[hermetic] blocked import name=ctypes
[hermetic] blocked native import spec=lxml._elementpath
```

## Composition with other guards

`--block-native` on its own only stops native loads — it doesn't
imply network or subprocess blocking. Combine flags explicitly:

```bash
# A reasonable LLM-tool sandbox.
hermetic --no-network --no-subprocess --block-native -- python tool_runner.py

# Or, equivalently:
hermetic --profile block-all -- python tool_runner.py
```

Combining `--no-subprocess` with `--block-native` activates the
extra import deny-list (`sh`, `pexpect`, `plumbum`, `sarge`,
`delegator`).

## Examples

```bash
# Run a tool that should not use any FFI.
hermetic --block-native -- python my_pure_tool.py
```

```python
from hermetic import with_hermetic

@with_hermetic(block_native=True)
def main():
    # If something tries `import ctypes`, this raises PolicyViolation.
    ...
```
