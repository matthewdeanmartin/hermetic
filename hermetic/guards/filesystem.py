# hermetic/guards/filesystem.py
from __future__ import annotations

import builtins
import os
import pathlib
from textwrap import dedent
from typing import Any

from ..errors import PolicyViolation

_installed = False
_originals: dict[str, Any] = {}
_root: str | None = None


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

    write_ops = ["remove", "rename", "replace", "unlink", "rmdir", "mkdir", "makedirs"]
    for name in write_ops:
        if hasattr(os, name):
            _originals[f"os.{name}"] = getattr(os, name)

    def _trace(msg: str):
        if trace:
            print(f"[hermetic] {msg}", flush=True)

    def open_guard(file, mode="r", *a, **k):
        path = str(file)
        if any(m in mode for m in ("w", "a", "x", "+")):
            _trace(f"blocked open write path={path}")
            raise PolicyViolation(f"filesystem readonly: {path}")
        if _root and not _is_within(path, _root):
            _trace(f"blocked open read-outside-root path={path}")
            raise PolicyViolation(f"read outside sandbox root: {path}")
        return _originals["open"](file, mode, *a, **k)  # type: ignore[misc]

    WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT

    def os_open_guard(path, flags, *a, **k):
        mode = "r" if not (flags & WRITE_FLAGS) else "w"
        return open_guard(path, mode, *a, **k)

    builtins.open = open_guard  # type: ignore[assignment]
    pathlib.Path.open = lambda self, *a, **k: open_guard(str(self), *a, **k)  # type: ignore[assignment]
    os.open = os_open_guard  # type: ignore[assignment]

    def _deny(*a: Any, **k: Any) -> None:
        _trace("blocked fs mutation")
        raise PolicyViolation("filesystem mutation disabled")

    for name in write_ops:
        if hasattr(os, name):
            setattr(os, name, _deny)


def uninstall() -> None:
    global _originals
    global _installed, _root
    if not _installed:
        return
    for k, v in _originals.items():
        if "." in k:
            mod_name, func_name = k.split(".", 1)
            if mod_name == "os":
                setattr(os, func_name, v)
            elif mod_name == "Path":
                setattr(pathlib.Path, func_name, v)
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
    WRITE_FLAGS = getattr(os, "O_WRONLY", 2) | getattr(os, "O_RDWR", 4) | getattr(os, "O_APPEND", 8) | getattr(os, "O_CREAT", 1)
    def os_open_guard(path, flags, *a, **k):
        mode = "r" if not (flags & WRITE_FLAGS) else "w"
        return _open_guard(path, mode, *a, **k)

    builtins.open = _open_guard
    pathlib.Path.open = lambda self,*a,**k: _open_guard(str(self), *a, **k)
    os.open = os_open_guard
    def _deny_fs(*a,**k): _tr("blocked fs mutation"); raise _HPolicy("fs mutation disabled")
    for name in ("remove","rename","replace","unlink","rmdir","mkdir","makedirs", "chmod", "chown"):
        if hasattr(os, name):
            setattr(os, name, _deny_fs)
"""
)
