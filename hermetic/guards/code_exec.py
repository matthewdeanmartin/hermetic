from __future__ import annotations

import ast
import builtins
import runpy
import sys
from textwrap import dedent
from typing import Any

from ..errors import PolicyViolation

_installed = False
_originals: dict[str, Any] = {}


def _caller_name(depth: int = 1) -> str:
    try:
        frame = sys._getframe(depth + 1)
    except ValueError:
        return ""
    return str(frame.f_globals.get("__name__", ""))


def _compile_is_internal(flags: int) -> bool:
    if flags & getattr(ast, "PyCF_ONLY_AST", 0):
        return True
    caller = _caller_name(2)
    return caller.startswith("importlib.")


def _runtime_exec_is_internal() -> bool:
    return _caller_name(2).startswith("importlib.")


def install(*, trace: bool = False) -> None:
    global _installed
    if _installed:
        return
    _installed = True

    _originals["eval"] = builtins.eval
    _originals["exec"] = builtins.exec
    _originals["compile"] = builtins.compile
    _originals["runpy.run_module"] = runpy.run_module
    _originals["runpy.run_path"] = runpy.run_path

    def _trace(msg: str) -> None:
        if trace:
            print(f"[hermetic] {msg}", file=sys.stderr, flush=True)

    def _deny_eval(*a: Any, **k: Any) -> None:
        _trace("blocked eval")
        raise PolicyViolation("dynamic code execution disabled: eval")

    def _guard_exec(*a: Any, **k: Any) -> Any:
        if _runtime_exec_is_internal():
            return _originals["exec"](*a, **k)
        _trace("blocked exec")
        raise PolicyViolation("dynamic code execution disabled: exec")

    def _guard_compile(
        source: Any,
        filename: str,
        mode: str,
        flags: int = 0,
        dont_inherit: bool = False,
        optimize: int = -1,
        **kwargs: Any,
    ) -> Any:
        if _compile_is_internal(flags):
            return _originals["compile"](
                source,
                filename,
                mode,
                flags,
                dont_inherit,
                optimize,
                **kwargs,
            )
        _trace("blocked compile")
        raise PolicyViolation("dynamic code execution disabled: compile")

    def _guard_run_module(*a: Any, **k: Any) -> Any:
        caller = _caller_name()
        if caller.startswith("hermetic."):
            return _originals["runpy.run_module"](*a, **k)
        _trace("blocked runpy.run_module")
        raise PolicyViolation("dynamic code execution disabled: run_module")

    def _guard_run_path(*a: Any, **k: Any) -> Any:
        caller = _caller_name()
        if caller.startswith("hermetic."):
            return _originals["runpy.run_path"](*a, **k)
        _trace("blocked runpy.run_path")
        raise PolicyViolation("dynamic code execution disabled: run_path")

    builtins.eval = _deny_eval
    builtins.exec = _guard_exec
    builtins.compile = _guard_compile  # type: ignore[assignment]
    runpy.run_module = _guard_run_module
    runpy.run_path = _guard_run_path


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    builtins.eval = _originals["eval"]
    builtins.exec = _originals["exec"]
    builtins.compile = _originals["compile"]
    runpy.run_module = _originals["runpy.run_module"]
    runpy.run_path = _originals["runpy.run_path"]
    _originals.clear()
    _installed = False


BOOTSTRAP_CODE = dedent(
    r"""
# --- dynamic code execution ---
if cfg.get("no_code_exec"):
    def _caller_name(depth=1):
        try:
            frame = sys._getframe(depth + 1)
        except ValueError:
            return ""
        return str(frame.f_globals.get("__name__", ""))

    def _compile_is_internal(flags):
        if flags & getattr(__import__("ast"), "PyCF_ONLY_AST", 0):
            return True
        return _caller_name(2).startswith("importlib.")

    def _runtime_exec_is_internal():
        return _caller_name(2).startswith("importlib.")

    _orig_eval = builtins.eval
    _orig_exec = builtins.exec
    _orig_compile = builtins.compile
    import runpy as _runpy
    _orig_run_module = _runpy.run_module
    _orig_run_path = _runpy.run_path

    def _deny_eval(*a, **k):
        _tr("blocked eval")
        raise _HPolicy("dynamic code execution disabled: eval")

    def _guard_exec(*a, **k):
        if _runtime_exec_is_internal():
            return _orig_exec(*a, **k)
        _tr("blocked exec")
        raise _HPolicy("dynamic code execution disabled: exec")

    def _guard_compile(source, filename, mode, flags=0, dont_inherit=False, optimize=-1, **kwargs):
        if _compile_is_internal(flags):
            return _orig_compile(source, filename, mode, flags, dont_inherit, optimize, **kwargs)
        _tr("blocked compile")
        raise _HPolicy("dynamic code execution disabled: compile")

    def _guard_run_module(*a, **k):
        if _caller_name().startswith("hermetic."):
            return _orig_run_module(*a, **k)
        _tr("blocked runpy.run_module")
        raise _HPolicy("dynamic code execution disabled: run_module")

    def _guard_run_path(*a, **k):
        if _caller_name().startswith("hermetic."):
            return _orig_run_path(*a, **k)
        _tr("blocked runpy.run_path")
        raise _HPolicy("dynamic code execution disabled: run_path")

    builtins.eval = _deny_eval
    builtins.exec = _guard_exec
    builtins.compile = _guard_compile
    _runpy.run_module = _guard_run_module
    _runpy.run_path = _guard_run_path
"""
)
