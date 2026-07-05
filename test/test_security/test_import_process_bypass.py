"""Regression tests for alternate import entry points and direct loaders."""

from __future__ import annotations

import _imp
import builtins
import importlib
import importlib.machinery as mach
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import zipfile
import zipimport
from pathlib import Path

import pytest

from hermetic.errors import PolicyViolation
from hermetic.bootstrap import _SITE_CUSTOMIZE
from hermetic.guards.imports_guard import install, uninstall


def _write_module(root: Path, name: str, value: int = 42) -> Path:
    """Create a small source module for import bypass probes."""
    path = root / f"{name}.py"
    path.write_text(f"VALUE = {value}\n", encoding="utf-8")
    return path


def _available_extension() -> tuple[str, str]:
    """Return an importable extension module name and path."""
    for entry in sys.path:
        root = Path(entry or ".")
        if not root.is_dir():
            continue
        for suffix in mach.EXTENSION_SUFFIXES:
            for path in root.glob(f"*{suffix}"):
                return path.name[: -len(suffix)], str(path)
    pytest.skip("no native extension module is available")


def test_importlib_import_module_checks_absolute_and_relative_names(
    tmp_path: Path,
) -> None:
    """Both forms of import_module must pass through the deny policy."""
    package = tmp_path / "guarded_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    _write_module(package, "blocked")
    sys.path.insert(0, str(tmp_path))
    importlib.import_module("guarded_pkg")

    install(block_native=False, deny_imports=["guarded_pkg.blocked"])
    try:
        with pytest.raises(PolicyViolation, match="guarded_pkg.blocked"):
            importlib.import_module("guarded_pkg.blocked")
        with pytest.raises(PolicyViolation, match="guarded_pkg.blocked"):
            importlib.import_module(".blocked", package="guarded_pkg")
    finally:
        uninstall()
        sys.path.remove(str(tmp_path))
        sys.modules.pop("guarded_pkg.blocked", None)
        sys.modules.pop("guarded_pkg", None)


def test_relative_fromlist_import_is_resolved_before_policy_check(
    tmp_path: Path,
) -> None:
    """Relative ``from . import name`` requests cannot hide the full name."""
    package = tmp_path / "relative_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    _write_module(package, "blocked")
    sys.path.insert(0, str(tmp_path))
    importlib.import_module("relative_pkg")

    install(block_native=False, deny_imports=["relative_pkg.blocked"])
    try:
        with pytest.raises(PolicyViolation, match="relative_pkg.blocked"):
            builtins.__import__(
                "",
                {"__package__": "relative_pkg", "__name__": "relative_pkg.caller"},
                fromlist=("blocked",),
                level=1,
            )
    finally:
        uninstall()
        sys.path.remove(str(tmp_path))
        sys.modules.pop("relative_pkg.blocked", None)
        sys.modules.pop("relative_pkg", None)


def test_source_file_loader_cannot_execute_denied_module(tmp_path: Path) -> None:
    """Direct SourceFileLoader execution must enforce denied names."""
    path = _write_module(tmp_path, "loader_blocked", value=73)
    loader = mach.SourceFileLoader("loader_blocked", str(path))
    spec = importlib.util.spec_from_loader("loader_blocked", loader)
    assert spec is not None

    install(block_native=False, deny_imports=["loader_blocked"])
    try:
        module = importlib.util.module_from_spec(spec)
        with pytest.raises(PolicyViolation, match="loader_blocked"):
            loader.exec_module(module)
    finally:
        uninstall()


def test_zipimporter_cannot_execute_denied_module(tmp_path: Path) -> None:
    """Direct zipimport execution must enforce denied names."""
    archive = tmp_path / "modules.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("zip_blocked.py", "VALUE = 99\n")
    loader = zipimport.zipimporter(str(archive))
    spec = loader.find_spec("zip_blocked")
    assert spec is not None

    install(block_native=False, deny_imports=["zip_blocked"])
    try:
        module = importlib.util.module_from_spec(spec)
        with pytest.raises(PolicyViolation, match="zip_blocked"):
            loader.exec_module(module)
    finally:
        uninstall()


def test_direct_pathfinder_cannot_return_native_extension_spec() -> None:
    """Calling PathFinder directly cannot bypass native-extension denial."""
    name, _ = _available_extension()
    install(block_native=True)
    try:
        with pytest.raises(PolicyViolation, match="native import blocked"):
            mach.PathFinder.find_spec(name)
    finally:
        uninstall()


def test_direct_extension_loader_and_imp_hooks_are_blocked() -> None:
    """Standard low-level native loading APIs must raise policy violations."""
    name, path = _available_extension()
    loader = mach.ExtensionFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None

    install(block_native=True)
    try:
        with pytest.raises(PolicyViolation, match="native import blocked"):
            importlib.util.module_from_spec(spec)
        with pytest.raises(PolicyViolation, match="native import blocked"):
            _imp.create_dynamic(spec)
    finally:
        uninstall()


def test_loader_guards_restore_after_uninstall(tmp_path: Path) -> None:
    """Uninstall restores direct loader behavior for later callers."""
    path = _write_module(tmp_path, "restored_loader", value=808)
    loader = mach.SourceFileLoader("restored_loader", str(path))
    spec = importlib.util.spec_from_loader("restored_loader", loader)
    assert spec is not None

    install(block_native=False, deny_imports=["restored_loader"])
    uninstall()

    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    assert module.VALUE == 808


def test_bootstrap_import_module_enforces_same_policy(tmp_path: Path) -> None:
    """Generated sitecustomize must mirror alternate-entry-point denial."""
    _write_module(tmp_path, "bootstrap_blocked")
    site_dir = Path(tempfile.mkdtemp(prefix="hermetic_bootstrap_test_"))
    (site_dir / "sitecustomize.py").write_text(_SITE_CUSTOMIZE, encoding="utf-8")
    env = os.environ.copy()
    env["HERMETIC_FLAGS_JSON"] = json.dumps(
        {"deny_imports": ["bootstrap_blocked"]}
    )
    env["PYTHONPATH"] = os.pathsep.join((str(site_dir), str(tmp_path)))
    code = (
        "import importlib\n"
        "try:\n"
        "    importlib.import_module('bootstrap_blocked')\n"
        "except RuntimeError:\n"
        "    print('BLOCKED')\n"
    )

    completed = subprocess.run(  # nosec: isolated interpreter regression probe
        [sys.executable, "-c", code],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "BLOCKED"
