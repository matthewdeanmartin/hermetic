# Import Policy Guard

Activated by repeated `--deny-import NAME` (CLI) or
`deny_imports=[...]` (API). Implemented in
`hermetic/guards/imports_guard.py`.

## What it patches

Hermetic checks Python's import hook, `importlib.import_module`,
`PathFinder.find_spec`, and the standard source, bytecode, and zip
loaders. It blocks any import whose resolved, fully qualified name
matches a denied module or package prefix.

Examples:

- `--deny-import pickle` blocks `pickle`
- `--deny-import xml.etree` blocks `xml.etree` and
  `xml.etree.ElementTree`

The check is dot-boundary aware, so denying `pickle` does not block an
unrelated module whose name merely starts with the same characters.

## Composition with native blocking

`--deny-import` composes with `--block-native`; both use the same
import-hook layer. The generic deny-list is user-supplied, while
`--block-native` adds Hermetic's built-in deny-lists for FFI and native
extension loading.

## What it does *not* catch

- **Captured module references** obtained before hermetic installed.
- **Already-imported modules** that user code still holds references to.
- **Arbitrary user-defined loaders** that execute code without using
  Python's standard loader implementations.

## Examples

```bash
hermetic --deny-import pickle --deny-import marshal -- python tool.py
```

```python
from hermetic import hermetic_blocker

with hermetic_blocker(deny_imports=["pickle", "xml.etree"]):
    ...
```
