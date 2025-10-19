# hermetic/guards/subprocess_guards.py
from __future__ import annotations
import os
import subprocess
import asyncio
from ..errors import PolicyViolation

_originals: dict[str, object] = {}
_installed = False

def install(*, trace: bool = False):
    global _installed
    if _installed:
        return
    _installed = True
    for name in ("Popen", "run", "call", "check_output"):
        _originals[name] = getattr(subprocess, name)
    _originals["system"] = os.system
    _originals["create_subprocess_exec"] = asyncio.create_subprocess_exec
    _originals["create_subprocess_shell"] = asyncio.create_subprocess_shell

    def _trace(msg: str):
        if trace:
            print(f"[hermetic] {msg}", flush=True)

    def _raise(*a, **k):
        _trace("blocked subprocess reason=no-subprocess")
        raise PolicyViolation("subprocess disabled")

    subprocess.Popen = _raise  # type: ignore[assignment]
    subprocess.run = _raise  # type: ignore[assignment]
    subprocess.call = _raise  # type: ignore[assignment]
    subprocess.check_output = _raise  # type: ignore[assignment]
    os.system = _raise  # type: ignore[assignment]
    asyncio.create_subprocess_exec = _raise  # type: ignore[assignment]
    asyncio.create_subprocess_shell = _raise  # type: ignore[assignment]

def uninstall():
    global _installed
    if not _installed:
        return
    subprocess.Popen = _originals["Popen"]  # type: ignore[assignment]
    subprocess.run = _originals["run"]  # type: ignore[assignment]
    subprocess.call = _originals["call"]  # type: ignore[assignment]
    subprocess.check_output = _originals["check_output"]  # type: ignore[assignment]
    os.system = _originals["system"]  # type: ignore[assignment]
    asyncio.create_subprocess_exec = _originals["create_subprocess_exec"]  # type: ignore[assignment]
    asyncio.create_subprocess_shell = _originals["create_subprocess_shell"]  # type: ignore[assignment]
    _installed = False
