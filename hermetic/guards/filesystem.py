# hermetic/guards/filesystem.py
from __future__ import annotations
import builtins
import os
import pathlib
from ..errors import PolicyViolation

_installed = False
_originals: dict[str, object] = {}
_root: str | None = None

def _norm(path: str) -> str:
    return os.path.realpath(path)

def _is_within(path: str, root: str) -> bool:
    p = _norm(path)
    r = _norm(root)
    return p == r or p.startswith(r + os.sep)

def install(*, fs_root: str | None = None, trace: bool = False):
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

    builtins.open = open_guard  # type: ignore[assignment]
    pathlib.Path.open = lambda self, *a, **k: open_guard(str(self), *a, **k)  # type: ignore[assignment]
    os.open = lambda path, flags, *a, **k: open_guard(path, "r" if flags & os.O_RDONLY else "w")  # type: ignore[assignment]

    def _deny(*a, **k):
        _trace("blocked fs mutation")
        raise PolicyViolation("filesystem mutation disabled")

    for name in write_ops:
        setattr(os, name, _deny)

def uninstall():
    global _installed, _root
    if not _installed:
        return
    builtins.open = _originals["open"]  # type: ignore[assignment]
    pathlib.Path.open = _originals["Path.open"]  # type: ignore[assignment]
    os.open = _originals["os.open"]  # type: ignore[assignment]

    write_ops = ["remove", "rename", "replace", "unlink", "rmdir", "mkdir", "makedirs"]
    for name in write_ops:
        setattr(os, name, _originals[f"os.{name}"])  # type: ignore[assignment]
    _installed, _root = False, None
