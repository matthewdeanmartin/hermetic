# hermetic/guards/import_guards.py
from __future__ import annotations
import builtins
import importlib.machinery as mach
from ..errors import PolicyViolation

_installed = False
_originals: dict[str, object] = {}

_DENY_NAMES = {"ctypes", "cffi"}

def install(*, trace: bool = False):
    """Deny native extension imports and FFI modules."""
    global _installed
    if _installed:
        return
    _installed = True
    _originals["ExtLoader"] = mach.ExtensionFileLoader
    _originals["__import__"] = builtins.__import__

    def _trace(msg: str):
        if trace:
            print(f"[hermetic] {msg}", flush=True)

    class GuardedExtLoader(mach.ExtensionFileLoader):  # type: ignore[misc]
        def create_module(self, spec):
            _trace(f"blocked native import spec={spec.name}")
            raise PolicyViolation(f"native import blocked: {spec.name}")

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split(".", 1)[0] in _DENY_NAMES:
            _trace(f"blocked import name={name}")
            raise PolicyViolation(f"import blocked: {name}")
        return _originals["__import__"](name, globals, locals, fromlist, level)  # type: ignore[misc]

    mach.ExtensionFileLoader = GuardedExtLoader  # type: ignore[assignment]
    builtins.__import__ = guarded_import  # type: ignore[assignment]

def uninstall():
    global _installed
    if not _installed:
        return
    mach.ExtensionFileLoader = _originals["ExtLoader"]  # type: ignore[assignment]
    builtins.__import__ = _originals["__import__"]  # type: ignore[assignment]
    _installed = False
