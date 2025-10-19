# tests/test_guards/test_imports_guard.py
import pytest
import builtins
from hermetic.guards.imports_guard import install, uninstall
from hermetic.errors import PolicyViolation

def test_imports_guard():
    install(trace=True)
    try:
        import math  # Allowed
        with pytest.raises(PolicyViolation, match="import blocked: ctypes"):
            import ctypes
    finally:
        uninstall()