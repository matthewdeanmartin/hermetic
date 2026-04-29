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


def test_imports_guard_deny_import_prefix():
    install(block_native=False, deny_imports=["pickle", "xml.etree"])
    try:
        with pytest.raises(PolicyViolation, match="import blocked: pickle"):
            __import__("pickle")

        with pytest.raises(
            PolicyViolation, match="import blocked: xml.etree.ElementTree"
        ):
            __import__("xml.etree.ElementTree", fromlist=["ElementTree"])
    finally:
        uninstall()
