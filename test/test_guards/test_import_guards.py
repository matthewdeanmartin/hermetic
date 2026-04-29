import importlib.machinery as mach
import sys

import pytest

from hermetic.blocker import hermetic_blocker
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


def test_imports_guard_meta_path_finder_blocks_native_specs(monkeypatch):
    loader = mach.ExtensionFileLoader("native_probe", "native_probe.pyd")
    spec = mach.ModuleSpec("native_probe", loader)

    install(trace=False)
    try:
        finder = sys.meta_path[0]
        monkeypatch.setattr(mach.PathFinder, "find_spec", lambda *args, **kwargs: spec)

        with pytest.raises(
            PolicyViolation, match="native import blocked: native_probe"
        ):
            finder.find_spec("native_probe")
    finally:
        uninstall()


def test_imports_guard_keeps_meta_path_guard_when_combined():
    with hermetic_blocker(block_native=True, block_interpreter_mutation=True):
        assert type(sys.meta_path[0]).__name__ == "_NativeExtensionFinder"

        with pytest.raises(PolicyViolation, match="sys.meta_path"):
            sys.meta_path.append(object())
