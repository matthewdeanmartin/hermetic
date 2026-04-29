# hermetic/guards/filesystem.py
from __future__ import annotations

import builtins
import io
import os
import pathlib
import sys
from textwrap import dedent
from typing import Any

from ..errors import PolicyViolation

_installed = False
_originals: dict[str, Any] = {}
_root: str | None = None

_PATH_WRITE_METHODS = (
    "chmod",
    "hardlink_to",
    "mkdir",
    "rename",
    "replace",
    "rmdir",
    "symlink_to",
    "touch",
    "unlink",
)


def _norm(path: str) -> str:
    return os.path.realpath(path)


def _is_within(path: str, root: str) -> bool:
    p = _norm(path)
    r = _norm(root)
    return p == r or p.startswith(r + os.sep)


def install(*, fs_root: str | None = None, trace: bool = False) -> None:
    """Readonly FS. Deny writes everywhere. Optionally require reads under fs_root."""
    global _installed, _root
    if _installed:
        return
    _installed, _root = True, fs_root

    _originals["open"] = builtins.open
    _originals["Path.open"] = pathlib.Path.open
    _originals["os.open"] = os.open
    _originals["io.open"] = io.open
    # posix.open is the C-level alias on POSIX; on Windows there's nt.open.
    for native_mod in ("posix", "nt"):
        nm = sys.modules.get(native_mod)
        if nm is not None and hasattr(nm, "open"):
            _originals[f"{native_mod}.open"] = nm.open

    for name in _PATH_WRITE_METHODS:
        if hasattr(pathlib.Path, name):
            _originals[f"Path.{name}"] = getattr(pathlib.Path, name)

    write_ops = [
        "remove",
        "rename",
        "replace",
        "unlink",
        "rmdir",
        "mkdir",
        "makedirs",
        "chmod",
        "chown",
        "link",
        "symlink",
        "truncate",
        "utime",
    ]
    for name in write_ops:
        if hasattr(os, name):
            _originals[f"os.{name}"] = getattr(os, name)

    def _trace(msg: str) -> None:
        if trace:
            print(f"[hermetic] {msg}", flush=True)

    def _coerce_path(p: Any) -> str:
        try:
            return str(os.fspath(p))
        except TypeError:
            return str(p)

    def open_guard(  # pylint: disable=keyword-arg-before-vararg
        file: Any, mode: str = "r", *a: Any, **k: Any
    ) -> Any:
        path = _coerce_path(file)
        # mode may be int (numeric flags) when open_guard is reached via
        # os.open; the os_open_guard already translated to a string in that
        # case. Defend anyway.
        mode_str = mode if isinstance(mode, str) else "r"
        if any(m in mode_str for m in ("w", "a", "x", "+")):
            _trace(f"blocked open write path={path}")
            raise PolicyViolation(f"filesystem readonly: {path}")
        if _root and not _is_within(path, _root):
            _trace(f"blocked open read-outside-root path={path}")
            raise PolicyViolation(f"read outside sandbox root: {path}")
        return _originals["open"](file, mode, *a, **k)

    WRITE_FLAGS = (
        os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_TRUNC", 0)
    )

    def os_open_guard(path: Any, flags: int, *a: Any, **k: Any) -> Any:
        mode = "r" if not (flags & WRITE_FLAGS) else "w"
        return open_guard(path, mode, *a, **k)

    builtins.open = open_guard
    pathlib.Path.open = lambda self, *a, **k: open_guard(str(self), *a, **k)  # type: ignore[method-assign]
    os.open = os_open_guard
    # io.open is documented as identical to builtins.open. Patch it too so
    # libraries that did `from io import open` get our guarded version.
    try:
        io.open = open_guard
    except (AttributeError, TypeError):
        pass
    for native_mod in ("posix", "nt"):
        nm = sys.modules.get(native_mod)
        if nm is not None and hasattr(nm, "open"):
            try:
                setattr(nm, "open", os_open_guard)
            except (AttributeError, TypeError):
                pass

    def _deny(*a: Any, **k: Any) -> None:  # pylint: disable=unused-argument
        _trace("blocked fs mutation")
        raise PolicyViolation("filesystem mutation disabled")

    for name in write_ops:
        if hasattr(os, name):
            setattr(os, name, _deny)
    for name in _PATH_WRITE_METHODS:
        if hasattr(pathlib.Path, name):
            setattr(pathlib.Path, name, _deny)

    # shutil mutators capture os.* references at call time in CPython, so
    # patching os is usually enough — but third-party reimplementations or
    # vendored copies may not. Patch the documented entry points directly.
    shutil_mod = sys.modules.get("shutil")
    if shutil_mod is None:
        try:
            import shutil as shutil_mod
        except Exception:
            shutil_mod = None
    if shutil_mod is not None:
        for name in (
            "rmtree",
            "move",
            "copy",
            "copy2",
            "copyfile",
            "copytree",
            "chown",
            "make_archive",
            "unpack_archive",
        ):
            if hasattr(shutil_mod, name):
                _originals[f"shutil.{name}"] = getattr(shutil_mod, name)
                try:
                    setattr(shutil_mod, name, _deny)
                except (AttributeError, TypeError):
                    pass


def uninstall() -> None:
    global _originals
    global _installed, _root
    if not _installed:
        return
    for k, v in _originals.items():
        if "." in k:
            mod_name, func_name = k.split(".", 1)
            if mod_name == "os":
                try:
                    setattr(os, func_name, v)
                except (AttributeError, TypeError):
                    pass
            elif mod_name == "Path":
                try:
                    setattr(pathlib.Path, func_name, v)
                except (AttributeError, TypeError):
                    pass
            elif mod_name == "io":
                try:
                    setattr(io, func_name, v)
                except (AttributeError, TypeError):
                    pass
            else:
                mod = sys.modules.get(mod_name)
                if mod is not None:
                    try:
                        setattr(mod, func_name, v)
                    except (AttributeError, TypeError):
                        pass
        else:
            setattr(builtins, k, v)

    _installed, _root, _originals = False, None, {}


# --- Code for bootstrap.py generation ---
BOOTSTRAP_CODE = dedent(
    r"""
# --- fs readonly ---
if cfg.get("fs_readonly"):
    ROOT = cfg.get("fs_root")
    _o = {"open": builtins.open, "Popen": pathlib.Path.open, "os.open": os.open}
    def _norm(p):
        try: import os as _os; return _os.path.realpath(p)
        except Exception: return p
    def _within(p, r):
        if not r: return False
        P, R = _norm(p), _norm(r)
        return P==R or P.startswith(R + ("/" if "/" in R else "\\"))
    def _open_guard(f, mode="r", *a, **k):
        path = str(f)
        if any(m in mode for m in ("w","a","x","+")): _tr(f"blocked open write path={path}"); raise _HPolicy("fs readonly")
        if ROOT and not _within(path, ROOT): _tr(f"blocked open read-outside-root path={path}"); raise _HPolicy("read outside root")
        return _o["open"](f, mode, *a, **k)
    WRITE_FLAGS = getattr(os, "O_WRONLY", 2) | getattr(os, "O_RDWR", 4) | getattr(os, "O_APPEND", 8) | getattr(os, "O_CREAT", 1) | getattr(os, "O_TRUNC", 0)
    def os_open_guard(path, flags, *a, **k):
        mode = "r" if not (flags & WRITE_FLAGS) else "w"
        return _open_guard(path, mode, *a, **k)

    builtins.open = _open_guard
    pathlib.Path.open = lambda self,*a,**k: _open_guard(str(self), *a, **k)
    os.open = os_open_guard
    def _deny_fs(*a,**k): _tr("blocked fs mutation"); raise _HPolicy("fs mutation disabled")
    for name in ("remove","rename","replace","unlink","rmdir","mkdir","makedirs","chmod","chown","link","symlink","truncate","utime"):
        if hasattr(os, name):
            setattr(os, name, _deny_fs)
    for name in ("chmod","hardlink_to","mkdir","rename","replace","rmdir","symlink_to","touch","unlink"):
        if hasattr(pathlib.Path, name):
            setattr(pathlib.Path, name, _deny_fs)
"""
)
