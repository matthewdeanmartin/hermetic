# hermetic/resolver.py
from __future__ import annotations

import importlib
import importlib.metadata
import os
import re
import runpy
import sys
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .util import which

SHEBANG_RE = re.compile(r"^#!\s*(\S+)(?:\s+.*)?$")


@dataclass
class TargetSpec:
    module: str
    attr: str  # "__main__" to run as script
    mode: str  # "inprocess" or "bootstrap"
    exe_path: Optional[str] = None
    interp_path: Optional[str] = None


def _console_entry(name: str) -> Optional[Tuple[str, str]]:
    eps = importlib.metadata.entry_points()
    try:
        group = eps.select(group="console_scripts")
    except Exception:
        group = [e for e in eps if getattr(e, "group", None) == "console_scripts"]
    for ep in group:
        if ep.name == name:
            if ":" in ep.value:
                m, a = ep.value.split(":", 1)
            else:
                m, a = ep.value, "__main__"
            return m, a
    return None


def _script_shebang(exe: str) -> Optional[str]:
    try:
        with open(exe, "rb") as f:
            first = f.readline().decode(errors="ignore")
        m = SHEBANG_RE.match(first)
        return m.group(1) if m else None
    except Exception:
        return None


def resolve(target: str) -> TargetSpec:
    # module:attr shortcut
    if ":" in target:
        m, a = target.split(":", 1)
        return TargetSpec(module=m, attr=a, mode="inprocess")

    # console script
    ep = _console_entry(target)
    if ep:
        exe = which(target)
        if exe:
            sheb = _script_shebang(exe)
            same = os.path.realpath(sys.executable) == os.path.realpath(
                sheb or sys.executable
            )
            return TargetSpec(
                module=ep[0],
                attr=ep[1],
                mode=("inprocess" if same else "bootstrap"),
                exe_path=exe,
                interp_path=sheb or sys.executable,
            )
        return TargetSpec(module=ep[0], attr=ep[1], mode="inprocess")

    # NEW: arbitrary PATH executable handling (python, py.exe, or any python-shebang script)
    exe = which(target)
    if exe:
        sheb = _script_shebang(exe)
        name = os.path.basename(exe).lower()
        looks_like_python = name in {"python", "python.exe", "py", "py.exe"}
        if looks_like_python or (sheb and "python" in os.path.basename(sheb).lower()):
            # We can bootstrap by injecting sitecustomize.
            return TargetSpec(
                module="",
                attr="__main__",
                mode="bootstrap",
                exe_path=exe,
                interp_path=sheb or exe,
            )

    # module as script (fallback)
    return TargetSpec(module=target, attr="__main__", mode="inprocess")


def invoke_inprocess(spec: TargetSpec) -> dict[Any, Any]:
    sys.modules.pop(spec.module, None)  # ensure fresh import after guards
    if spec.attr == "__main__":
        return runpy.run_module(spec.module, run_name="__main__")
    mod = importlib.import_module(spec.module)
    func = getattr(mod, spec.attr)
    if callable(func):
        return func()
    # Fallback: execute module as script
    return runpy.run_module(spec.module, run_name="__main__")
