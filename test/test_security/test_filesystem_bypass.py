"""Phase 4 hardening tests: io.open, shutil mutators."""

from __future__ import annotations

import io
import shutil

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.filesystem import install, uninstall


def test_io_open_write_blocked(tmp_path):
    install(fs_root=None, trace=False)
    try:
        with pytest.raises(PolicyViolation, match="filesystem readonly"):
            io.open(str(tmp_path / "x.txt"), "w")
    finally:
        uninstall()


def test_shutil_rmtree_blocked(tmp_path):
    target = tmp_path / "victim"
    target.mkdir()
    install(fs_root=None, trace=False)
    try:
        with pytest.raises(PolicyViolation, match="filesystem mutation"):
            shutil.rmtree(str(target))
    finally:
        uninstall()
    # cleanup outside guard
    if target.exists():
        shutil.rmtree(str(target))


def test_shutil_move_blocked(tmp_path):
    src = tmp_path / "a"
    src.write_text("hi")
    install(fs_root=None, trace=False)
    try:
        with pytest.raises(PolicyViolation, match="filesystem mutation"):
            shutil.move(str(src), str(tmp_path / "b"))
    finally:
        uninstall()
