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

    targets = {
        subprocess: ("Popen", "run", "call", "check_output"),
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
        ),
        asyncio: ("create_subprocess_exec", "create_subprocess_shell"),
    }

    for mod, funcs in targets.items():
        for name in funcs:
            if hasattr(mod, name):
                _originals[f"{mod.__name__}.{name}"] = getattr(mod, name)

    def _trace(msg: str) -> None:
        if trace:
            print(f"[hermetic] {msg}", flush=True)

    def _raise(*a: Any, **k: Any) -> Never:
        _trace("blocked subprocess reason=no-subprocess")
        raise PolicyViolation("subprocess disabled")

    for mod, funcs in targets.items():
        for name in funcs:
            if hasattr(mod, name):
                setattr(mod, name, _raise)


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    for key, original_func in _originals.items():
        mod_name, func_name = key.split(".", 1)
        mod = sys.modules[mod_name]
        setattr(mod, func_name, original_func)
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
    }
    for mod_name, funcs in targets.items():
        try:
            mod = __import__(mod_name)
            for name in funcs:
                if hasattr(mod, name):
                    setattr(mod, name, _deny_exec)
        except ImportError:
            pass
"""
)
