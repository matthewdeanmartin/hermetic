"""Phase 1 hardening tests: ctypes / cffi import & attribute denial."""
from __future__ import annotations

import sys

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.imports_guard import install, uninstall


def test_block_native_denies_ctypes_import():
    install(trace=False)
    try:
        sys.modules.pop("ctypes", None)
        with pytest.raises(PolicyViolation, match="import blocked: ctypes"):
            import ctypes  # noqa: F401
    finally:
        uninstall()


def test_block_native_denies_underscore_ctypes_import():
    install(trace=False)
    try:
        sys.modules.pop("_ctypes", None)
        with pytest.raises(PolicyViolation, match="import blocked: _ctypes"):
            import _ctypes  # noqa: F401
    finally:
        uninstall()


def test_already_loaded_ctypes_attrs_are_neutered():
    # Pre-load ctypes outside the guard.
    import ctypes  # noqa: F401

    install(trace=False)
    try:
        ct = sys.modules["ctypes"]
        with pytest.raises(PolicyViolation, match="native interface blocked"):
            ct.CDLL("nonexistent")
    finally:
        uninstall()


def test_subprocess_lib_block_optional():
    # Default: do not block sh/pexpect by name.
    install(trace=False, block_subprocess_libs=False)
    try:
        # We're not asking it to load — just verify it's not on the deny list.
        import importlib

        # importing 'json' (a common stdlib) should still work
        importlib.import_module("json")
    finally:
        uninstall()

    # With the flag, 'sh' is denied.
    install(trace=False, block_subprocess_libs=True)
    try:
        with pytest.raises(PolicyViolation, match="import blocked: sh"):
            __import__("sh")
    finally:
        uninstall()
