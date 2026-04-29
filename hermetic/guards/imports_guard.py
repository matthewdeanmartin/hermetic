# hermetic/guards/imports_guard.py
from __future__ import annotations

import builtins
import importlib
import importlib.machinery as mach
import sys
from textwrap import dedent
from typing import Any, Iterable

from ..errors import PolicyViolation

_installed = False
_originals: dict[str, Any] = {}

# Names whose top-level package import is blocked when block_native is on.
# We block the FFI surface plus ctypes' private siblings — without these,
# attackers can re-create CDLL/PyDLL/etc.
_DENY_NAMES = {
    "ctypes",
    "_ctypes",
    "cffi",
    "_cffi_backend",
}

# Subprocess-replacement libraries: these wrap subprocess.Popen and friends,
# but many of them capture references at import time, so blocking the import
# is more reliable than patching them after the fact. Only enabled when the
# subprocess guard is also requested.
_SUBPROC_REPLACEMENT_NAMES = {
    "sh",
    "pexpect",
    "plumbum",
    "sarge",
    "delegator",
}

_CTYPES_ATTRS = ("CDLL", "PyDLL", "WinDLL", "OleDLL", "LibraryLoader")
_CTYPES_LOADER_ATTRS = ("cdll", "pydll", "windll", "oledll")
_CTYPES_UTIL_ATTRS = ("find_library", "find_msvcrt")
_CFFI_ATTRS = ("FFI", "dlopen", "verify")


def _deny_use(name: str) -> Any:
    raise PolicyViolation(f"native interface blocked: {name}")


def _patch_module_attrs(mod_name: str, attrs: tuple[str, ...]) -> None:
    """Best-effort: replace `mod.<attr>` with a denier on each named attribute."""
    mod = sys.modules.get(mod_name)
    if mod is None:
        return
    for attr in attrs:
        if hasattr(mod, attr):
            key = f"{mod_name}.{attr}"
            if key not in _originals:
                _originals[key] = getattr(mod, attr)
            try:
                setattr(
                    mod,
                    attr,
                    lambda *a, _name=f"{mod_name}.{attr}", **k: _deny_use(_name),
                )
            except (AttributeError, TypeError):
                # Some C-level attributes are read-only; skip them.
                pass


def _patch_loaded_native_modules() -> None:
    _patch_module_attrs("ctypes", _CTYPES_ATTRS + _CTYPES_LOADER_ATTRS)
    _patch_module_attrs("ctypes.util", _CTYPES_UTIL_ATTRS)
    _patch_module_attrs("cffi", _CFFI_ATTRS)


def _invalidate_finder_caches() -> None:
    """Force importlib to re-walk path hooks so our subclassed loader
    is used for any subsequent native-extension import."""
    try:
        importlib.invalidate_caches()
    except Exception:  # nosec: B110:try_except_pass
        pass


def _normalize_deny_names(names: Iterable[str]) -> set[str]:
    return {name.strip() for name in names if name and name.strip()}


def _matches_denied_import(name: str, denied_name: str) -> bool:
    root = name.split(".", 1)[0]
    return (
        name == denied_name
        or name.startswith(f"{denied_name}.")
        or root == denied_name
    )


def install(
    *,
    block_native: bool = True,
    trace: bool = False,
    block_subprocess_libs: bool = False,
    deny_imports: Iterable[str] = (),
) -> None:
    """Deny native extension imports and FFI modules.

    Set `block_subprocess_libs=True` to additionally deny imports of
    common subprocess-replacement libraries (sh, pexpect, plumbum,
    sarge, delegator). Off by default so that block_native alone
    doesn't punish unit-test users.
    """
    global _installed
    if _installed:
        return
    _installed = True
    _originals["__import__"] = builtins.__import__
    if block_native:
        _originals["ExtLoader"] = mach.ExtensionFileLoader

    deny_names = _normalize_deny_names(deny_imports)
    if block_native:
        deny_names |= _DENY_NAMES
    if block_native and block_subprocess_libs:
        deny_names |= _SUBPROC_REPLACEMENT_NAMES

    def _trace(msg: str) -> None:
        if trace:
            print(f"[hermetic] {msg}", flush=True)

    if block_native:

        class GuardedExtLoader(mach.ExtensionFileLoader):
            def create_module(self, spec: Any) -> Any:
                _trace(f"blocked native import spec={spec.name}")
                raise PolicyViolation(f"native import blocked: {spec.name}")

    def guarded_import(
        name: str,
        globals: Any = None,  # pylint: disable=redefined-builtin
        locals: Any = None,  # pylint: disable=redefined-builtin
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if any(_matches_denied_import(name, denied_name) for denied_name in deny_names):
            _trace(f"blocked import name={name}")
            raise PolicyViolation(f"import blocked: {name}")
        return _originals["__import__"](name, globals, locals, fromlist, level)

    if block_native:
        mach.ExtensionFileLoader = GuardedExtLoader  # type: ignore[misc]
    builtins.__import__ = guarded_import
    if block_native:
        _patch_loaded_native_modules()
        _invalidate_finder_caches()


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    if "ExtLoader" in _originals:
        mach.ExtensionFileLoader = _originals.pop("ExtLoader")  # type: ignore[misc]
    builtins.__import__ = _originals.pop("__import__")
    for key in list(_originals):
        mod_name, attr = key.split(".", 1)
        mod = sys.modules.get(mod_name)
        if mod is not None:
            try:
                setattr(mod, attr, _originals.pop(key))
            except (AttributeError, TypeError):
                _originals.pop(key, None)
        else:
            _originals.pop(key, None)
    _invalidate_finder_caches()
    _installed = False


# --- Code for bootstrap.py generation ---
BOOTSTRAP_CODE = dedent(
    r"""
# --- strict imports ---
if cfg.get("block_native") or cfg.get("deny_imports"):
    _origExt = mach.ExtensionFileLoader
    _origImp = builtins.__import__
    _BLOCK_NATIVE = bool(cfg.get("block_native"))
    _BLOCK_SUBPROC_LIBS = bool(cfg.get("no_subprocess"))
    _DENY = set([n for n in cfg.get("deny_imports", []) if n])
    if _BLOCK_NATIVE:
        _DENY |= {"ctypes","_ctypes","cffi","_cffi_backend"}
    if _BLOCK_NATIVE and _BLOCK_SUBPROC_LIBS:
        _DENY |= {"sh","pexpect","plumbum","sarge","delegator"}
    def _trimp(n): _tr(f"blocked import name={n}")
    def _deny_native_use(name): raise _HPolicy(f"native interface blocked: {name}")
    def _match_import(name, denied):
        root = name.split(".", 1)[0]
        return name == denied or name.startswith(denied + ".") or root == denied
    def _patch_attrs(mod_name, attrs):
        m = sys.modules.get(mod_name)
        if m is None: return
        for a in attrs:
            if hasattr(m, a):
                try: setattr(m, a, lambda *_a, _n=f"{mod_name}.{a}", **_k: _deny_native_use(_n))
                except (AttributeError, TypeError): pass
    def _patch_loaded_native_modules():
        _patch_attrs("ctypes", ("CDLL","PyDLL","WinDLL","OleDLL","LibraryLoader","cdll","pydll","windll","oledll"))
        _patch_attrs("ctypes.util", ("find_library","find_msvcrt"))
        _patch_attrs("cffi", ("FFI","dlopen","verify"))
    class GuardedExtLoader(_origExt):
        def create_module(self, spec): _tr(f"blocked native import spec={spec.name}"); raise _HPolicy("native import blocked")
    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if any(_match_import(name, denied) for denied in _DENY): _trimp(name); raise _HPolicy("import blocked")
        return _origImp(name, globals, locals, fromlist, level)
    if _BLOCK_NATIVE:
        mach.ExtensionFileLoader = GuardedExtLoader
    builtins.__import__ = guarded_import
    if _BLOCK_NATIVE:
        _patch_loaded_native_modules()
        try:
            import importlib as _il; _il.invalidate_caches()
        except Exception: pass
"""
)
