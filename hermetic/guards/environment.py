from __future__ import annotations

import os
import sys
from collections.abc import Iterator, MutableMapping
from textwrap import dedent
from typing import Any

try:
    from typing import Never
except ImportError:
    from typing_extensions import Never

from ..errors import PolicyViolation

_installed = False
_originals: dict[str, Any] = {}


class _GuardedEnviron(MutableMapping[str, str]):
    def __init__(self, backing: MutableMapping[str, str], trace: bool = False) -> None:
        self._backing = backing
        self._trace_enabled = trace

    def _trace(self, msg: str) -> None:
        if self._trace_enabled:
            print(f"[hermetic] {msg}", file=sys.stderr, flush=True)

    def _deny_read(self) -> Never:
        self._trace("blocked environment read")
        raise PolicyViolation("environment disabled")

    def _deny_write(self) -> Never:
        self._trace("blocked environment mutation")
        raise PolicyViolation("environment mutation disabled")

    def __getitem__(self, key: str) -> str:
        return self._deny_read()

    def __setitem__(self, key: str, value: str) -> None:
        self._deny_write()

    def __delitem__(self, key: str) -> None:
        self._deny_write()

    def __iter__(self) -> Iterator[str]:  # pylint: disable=non-iterator-returned
        return self._deny_read()

    def __len__(self) -> int:  # pylint: disable=invalid-length-returned
        return self._deny_read()

    def get(self, key: str, default: Any = None) -> Any:
        return self._deny_read()

    def copy(self) -> dict[str, str]:
        return self._deny_read()

    def items(self) -> Any:
        return self._deny_read()

    def keys(self) -> Any:
        return self._deny_read()

    def values(self) -> Any:
        return self._deny_read()

    def __contains__(self, key: object) -> bool:
        return self._deny_read()

    def pop(self, key: str, default: Any = None) -> Any:
        return self._deny_write()

    def popitem(self) -> tuple[str, str]:
        return self._deny_write()

    def clear(self) -> None:
        self._deny_write()

    def setdefault(self, key: str, default: Any = None) -> Any:
        self._deny_write()

    def update( # pylint: disable=arguments-differ,unused-argument
        self, # pylint: disable=arguments-differ,unused-argument
        *args: Any,  # pylint: disable=arguments-differ,unused-argument
        **kwargs: Any,  # pylint: disable=arguments-differ,unused-argument
    ) -> None:
        self._deny_write()

    def __repr__(self) -> str:  # pylint: disable=invalid-repr-returned
        return self._deny_read()


def install(*, trace: bool = False) -> None:
    global _installed
    if _installed:
        return
    _installed = True

    _originals["os.environ"] = os.environ
    _originals["os.getenv"] = os.getenv
    _originals["os.putenv"] = os.putenv
    _originals["os.unsetenv"] = os.unsetenv

    def _trace(msg: str) -> None:
        if trace:
            print(f"[hermetic] {msg}", file=sys.stderr, flush=True)

    def _deny_read(*a: Any, **k: Any) -> None:  # pylint: disable=unused-argument
        _trace("blocked environment read")
        raise PolicyViolation("environment disabled")

    def _deny_write(*a: Any, **k: Any) -> None:  # pylint: disable=unused-argument
        _trace("blocked environment mutation")
        raise PolicyViolation("environment mutation disabled")

    os.environ = _GuardedEnviron(os.environ, trace=trace)  # type: ignore[assignment]
    if hasattr(os, "environb"):
        _originals["os.environb"] = os.environb
        os.environb = _GuardedEnviron(os.environb, trace=trace)
    os.getenv = _deny_read  # type: ignore[assignment]
    os.putenv = _deny_write
    os.unsetenv = _deny_write


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    os.environ = _originals["os.environ"]
    os.getenv = _originals["os.getenv"]
    os.putenv = _originals["os.putenv"]
    os.unsetenv = _originals["os.unsetenv"]
    if "os.environb" in _originals and hasattr(os, "environb"):
        os.environb = _originals["os.environb"]
    _originals.clear()
    _installed = False


BOOTSTRAP_CODE = dedent(
    r"""
# --- environment ---
if cfg.get("no_environment"):
    class _GuardedEnviron:
        def __init__(self, trace_enabled=False):
            self._trace_enabled = trace_enabled
        def _trace(self, msg):
            if self._trace_enabled:
                print(f"[hermetic] {msg}", file=sys.stderr, flush=True)
        def _deny_read(self):
            self._trace("blocked environment read")
            raise _HPolicy("environment disabled")
        def _deny_write(self):
            self._trace("blocked environment mutation")
            raise _HPolicy("environment mutation disabled")
        def __getitem__(self, key): self._deny_read()
        def __setitem__(self, key, value): self._deny_write()
        def __delitem__(self, key): self._deny_write()
        def __iter__(self): self._deny_read()
        def __len__(self): self._deny_read()
        def get(self, key, default=None): self._deny_read()
        def copy(self): self._deny_read()
        def items(self): self._deny_read()
        def keys(self): self._deny_read()
        def values(self): self._deny_read()
        def __contains__(self, key): self._deny_read()
        def pop(self, key, default=None): self._deny_write()
        def popitem(self): self._deny_write()
        def clear(self): self._deny_write()
        def setdefault(self, key, default=None): self._deny_write()
        def update(self, *args, **kwargs): self._deny_write()
        def __repr__(self): self._deny_read()

    def _deny_env_read(*a, **k):
        _tr("blocked environment read")
        raise _HPolicy("environment disabled")

    def _deny_env_write(*a, **k):
        _tr("blocked environment mutation")
        raise _HPolicy("environment mutation disabled")

    os.environ = _GuardedEnviron(trace_enabled=trace)
    if hasattr(os, "environb"):
        os.environb = _GuardedEnviron(trace_enabled=trace)
    os.getenv = _deny_env_read
    os.putenv = _deny_env_write
    os.unsetenv = _deny_env_write
"""
)
