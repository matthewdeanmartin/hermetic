from __future__ import annotations

import os
import site
import sys
from textwrap import dedent
from typing import Any, SupportsIndex

try:
    from typing import Never
except ImportError:
    from typing_extensions import Never

from ..errors import PolicyViolation

_installed = False
_originals: dict[str, Any] = {}


class _GuardedList(list[Any]):
    def __init__(self, values: list[Any], label: str, trace: bool = False) -> None:
        super().__init__(values)
        self._label = label
        self._trace_enabled = trace

    def _deny(self) -> Never:
        if self._trace_enabled:
            print(
                f"[hermetic] blocked {self._label} mutation",
                file=sys.stderr,
                flush=True,
            )
        raise PolicyViolation(f"interpreter mutation disabled: {self._label}")

    def append(self, item: Any) -> None:  # pylint: disable=unused-argument
        self._deny()

    def extend(self, values: Any) -> None:  # pylint: disable=unused-argument
        self._deny()

    def insert(
        self, index: SupportsIndex, item: Any  # pylint: disable=unused-argument
    ) -> None:
        self._deny()

    def pop(self, index: SupportsIndex = -1) -> Any:  # pylint: disable=unused-argument
        return self._deny()

    def remove(self, item: Any) -> None:  # pylint: disable=unused-argument
        self._deny()

    def clear(self) -> None:
        self._deny()

    def sort(
        self, *args: Any, **kwargs: Any  # pylint: disable=unused-argument
    ) -> None:
        self._deny()

    def reverse(self) -> None:
        self._deny()

    def __setitem__(self, key: Any, value: Any) -> None:
        self._deny()

    def __delitem__(self, key: Any) -> None:
        self._deny()

    def __iadd__(self, other: Any) -> "_GuardedList":  # type: ignore[misc]
        return self._deny()

    def __imul__(self, other: Any) -> "_GuardedList":  # type: ignore[misc]
        return self._deny()


class _GuardedDict(dict[Any, Any]):
    def __init__(self, values: dict[Any, Any], label: str, trace: bool = False) -> None:
        super().__init__(values)
        self._label = label
        self._trace_enabled = trace

    def _deny(self) -> Never:
        if self._trace_enabled:
            print(
                f"[hermetic] blocked {self._label} mutation",
                file=sys.stderr,
                flush=True,
            )
        raise PolicyViolation(f"interpreter mutation disabled: {self._label}")

    def __setitem__(self, key: Any, value: Any) -> None:
        self._deny()

    def __delitem__(self, key: Any) -> None:
        self._deny()

    def clear(self) -> None:
        self._deny()

    def pop(
        self, key: Any, default: Any = None  # pylint: disable=unused-argument
    ) -> Any:
        return self._deny()

    def popitem(self) -> tuple[Any, Any]:
        return self._deny()

    def setdefault(
        self, key: Any, default: Any = None  # pylint: disable=unused-argument
    ) -> Any:
        self._deny()

    def update(
        self, *args: Any, **kwargs: Any  # pylint: disable=unused-argument
    ) -> None:
        self._deny()


def install(*, trace: bool = False) -> None:
    global _installed
    if _installed:
        return
    _installed = True

    _originals["sys.path"] = sys.path
    _originals["sys.meta_path"] = sys.meta_path
    _originals["sys.path_hooks"] = sys.path_hooks
    _originals["sys.path_importer_cache"] = sys.path_importer_cache
    _originals["os.chdir"] = os.chdir
    if hasattr(os, "fchdir"):
        _originals["os.fchdir"] = os.fchdir
    _originals["site.addsitedir"] = site.addsitedir

    def _trace(msg: str) -> None:
        if trace:
            print(f"[hermetic] {msg}", file=sys.stderr, flush=True)

    def _deny_chdir(*a: Any, **k: Any) -> None:  # pylint: disable=unused-argument
        _trace("blocked os.chdir")
        raise PolicyViolation("interpreter mutation disabled: chdir")

    def _deny_fchdir(*a: Any, **k: Any) -> None:  # pylint: disable=unused-argument
        _trace("blocked os.fchdir")
        raise PolicyViolation("interpreter mutation disabled: fchdir")

    def _deny_addsitedir(*a: Any, **k: Any) -> None:  # pylint: disable=unused-argument
        _trace("blocked site.addsitedir")
        raise PolicyViolation("interpreter mutation disabled: addsitedir")

    sys.path = _GuardedList(list(sys.path), "sys.path", trace=trace)
    sys.meta_path = _GuardedList(list(sys.meta_path), "sys.meta_path", trace=trace)
    sys.path_hooks = _GuardedList(list(sys.path_hooks), "sys.path_hooks", trace=trace)
    sys.path_importer_cache = _GuardedDict(
        dict(sys.path_importer_cache), "sys.path_importer_cache", trace=trace
    )
    os.chdir = _deny_chdir
    if hasattr(os, "fchdir"):
        os.fchdir = _deny_fchdir
    site.addsitedir = _deny_addsitedir


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    sys.path = _originals["sys.path"]
    sys.meta_path = _originals["sys.meta_path"]
    sys.path_hooks = _originals["sys.path_hooks"]
    sys.path_importer_cache = _originals["sys.path_importer_cache"]
    os.chdir = _originals["os.chdir"]
    if "os.fchdir" in _originals and hasattr(os, "fchdir"):
        os.fchdir = _originals["os.fchdir"]
    site.addsitedir = _originals["site.addsitedir"]
    _originals.clear()
    _installed = False


BOOTSTRAP_CODE = dedent(
    r"""
# --- interpreter mutation ---
if cfg.get("no_interpreter_mutation"):
    import site as _site

    class _GuardedList(list):
        def __init__(self, values, label):
            super().__init__(values)
            self._label = label
        def _deny(self):
            _tr(f"blocked {self._label} mutation")
            raise _HPolicy(f"interpreter mutation disabled: {self._label}")
        def append(self, item): self._deny()
        def extend(self, values): self._deny()
        def insert(self, index, item): self._deny()
        def pop(self, index=-1): self._deny()
        def remove(self, item): self._deny()
        def clear(self): self._deny()
        def sort(self, *args, **kwargs): self._deny()
        def reverse(self): self._deny()
        def __setitem__(self, key, value): self._deny()
        def __delitem__(self, key): self._deny()
        def __iadd__(self, other): self._deny()
        def __imul__(self, other): self._deny()

    class _GuardedDict(dict):
        def __init__(self, values, label):
            super().__init__(values)
            self._label = label
        def _deny(self):
            _tr(f"blocked {self._label} mutation")
            raise _HPolicy(f"interpreter mutation disabled: {self._label}")
        def __setitem__(self, key, value): self._deny()
        def __delitem__(self, key): self._deny()
        def clear(self): self._deny()
        def pop(self, key, default=None): self._deny()
        def popitem(self): self._deny()
        def setdefault(self, key, default=None): self._deny()
        def update(self, *args, **kwargs): self._deny()

    def _deny_chdir(*a, **k):
        _tr("blocked os.chdir")
        raise _HPolicy("interpreter mutation disabled: chdir")

    def _deny_fchdir(*a, **k):
        _tr("blocked os.fchdir")
        raise _HPolicy("interpreter mutation disabled: fchdir")

    def _deny_addsitedir(*a, **k):
        _tr("blocked site.addsitedir")
        raise _HPolicy("interpreter mutation disabled: addsitedir")

    sys.path = _GuardedList(list(sys.path), "sys.path")
    sys.meta_path = _GuardedList(list(sys.meta_path), "sys.meta_path")
    sys.path_hooks = _GuardedList(list(sys.path_hooks), "sys.path_hooks")
    sys.path_importer_cache = _GuardedDict(dict(sys.path_importer_cache), "sys.path_importer_cache")
    os.chdir = _deny_chdir
    if hasattr(os, "fchdir"):
        os.fchdir = _deny_fchdir
    _site.addsitedir = _deny_addsitedir
"""
)
