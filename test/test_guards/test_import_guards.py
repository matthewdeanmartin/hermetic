# tests/test_guards/test_imports_guard.py

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.imports_guard import install, uninstall


def test_imports_guard():
    install(trace=True)
    try:

        with pytest.raises(PolicyViolation, match="import blocked: ctypes"):
            import ctypes

            assert dir(ctypes)
    finally:
        uninstall()
