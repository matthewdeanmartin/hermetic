# hermetic/guards/subprocess_guard.py
from __future__ import annotations

import asyncio
import os
import subprocess  # nosec
import sys
from textwrap import dedent
from typing import Any, Never

from ..errors import PolicyViolation

_originals: dict[str, object] = {}
_installed = False


def install(*, trace: bool = False) -> None:
    global _installed
    if _installed:
        return
    _installed = True

    targets: dict[Any, tuple[str, ...]] = {
        subprocess: (
            "Popen",
            "run",
            "call",
            "check_output",
            "check_call",
            "getoutput",
            "getstatusoutput",
        ),
        os: (
            "system",
            "execv",
            "execve",
            "execl",
            "execle",
            "execlp",
            "execlpe",
            "execvp",
            "execvpe",
            "fork",
            "forkpty",
            "spawnl",
            "spawnle",
            "spawnlp",
            "spawnlpe",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
            "posix_spawn",
            "posix_spawnp",
            "startfile",
        ),
        asyncio: ("create_subprocess_exec", "create_subprocess_shell"),
    }

    # Best-effort: also patch the C-level primitives. Without these,
    # any caller that re-implements Popen reaches them directly.
    # _posixsubprocess.fork_exec is the underlying primitive on POSIX;
    # _winapi.CreateProcess is the equivalent on Windows.
    extra_modules: list[tuple[str, tuple[str, ...]]] = [
        ("_posixsubprocess", ("fork_exec",)),
        ("posix", ("fork", "forkpty", "system", "posix_spawn", "posix_spawnp")),
        ("pty", ("fork", "spawn", "openpty")),
        ("_winapi", ("CreateProcess",)),
    ]
    for mod_name, fns in extra_modules:
        mod = sys.modules.get(mod_name)
        if mod is None:
            try:
                mod = __import__(mod_name)
            except Exception:
                mod = None
        if mod is not None:
            targets[mod] = fns

    # Multiprocessing — block Process.start (the public entry point) so we
    # don't have to enumerate every spawn/fork backend.
    try:
        import multiprocessing as _mp

        _originals["multiprocessing.Process.start"] = _mp.Process.start
    except Exception:
        _mp = None  # type: ignore[assignment]

    for mod, funcs in targets.items():
        for name in funcs:
            if hasattr(mod, name):
                _originals[f"{mod.__name__}.{name}"] = getattr(mod, name)

    def _trace(msg: str) -> None:
        if trace:
            print(f"[hermetic] {msg}", flush=True)

    def _raise(*a: Any, **k: Any) -> Never:  # pylint: disable=unused-argument
        _trace("blocked subprocess reason=no-subprocess")
        raise PolicyViolation("subprocess disabled")

    for mod, funcs in targets.items():
        for name in funcs:
            if hasattr(mod, name):
                try:
                    setattr(mod, name, _raise)
                except (AttributeError, TypeError):
                    # Some C-level slots are read-only; skip.
                    pass

    if _mp is not None:
        try:
            _mp.Process.start = _raise  # type: ignore[method-assign]
        except (AttributeError, TypeError):
            pass


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    for key, original_func in _originals.items():
        # Special-case nested attribute (e.g., multiprocessing.Process.start)
        if key == "multiprocessing.Process.start":
            mp = sys.modules.get("multiprocessing")
            if mp is not None:
                try:
                    mp.Process.start = original_func
                except (AttributeError, TypeError):
                    pass
            continue
        mod_name, func_name = key.split(".", 1)
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        try:
            setattr(mod, func_name, original_func)
        except (AttributeError, TypeError):
            pass
    _installed = False
    _originals.clear()


# --- Code for bootstrap.py generation ---
BOOTSTRAP_CODE = dedent(
    r"""
# --- subprocess ---
if cfg.get("no_subprocess"):
    def _deny_exec(*a,**k): _tr("blocked subprocess reason=no-subprocess"); raise _HPolicy("subprocess disabled")
    targets = {
        "subprocess": ("Popen", "run", "call", "check_output"),
        "os": ("system", "execv", "execve", "execl", "execle", "execlp", "execlpe", "execvp", "execvpe", "fork", "forkpty", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe"),
        "asyncio": ("create_subprocess_exec", "create_subprocess_shell"),
        # C-level primitives — POSIX and Windows.
        "_posixsubprocess": ("fork_exec",),
        "_winapi": ("CreateProcess",),
    }
    for mod_name, funcs in targets.items():
        try:
            mod = __import__(mod_name)
            for name in funcs:
                if hasattr(mod, name):
                    try: setattr(mod, name, _deny_exec)
                    except (AttributeError, TypeError): pass
        except ImportError:
            pass
"""
)
