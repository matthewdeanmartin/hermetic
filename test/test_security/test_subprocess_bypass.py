"""Phase 3 hardening tests: _posixsubprocess and shutil-style entry points."""
from __future__ import annotations

import os
import sys

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.subprocess_guard import install, uninstall


def test_posix_spawn_blocked():
    if not hasattr(os, "posix_spawn"):
        pytest.skip("os.posix_spawn not available on this platform")
    install(trace=False)
    try:
        with pytest.raises(PolicyViolation, match="subprocess"):
            os.posix_spawn("/bin/true", ["/bin/true"], os.environ)
    finally:
        uninstall()


def test_posixsubprocess_blocked():
    if "_posixsubprocess" not in sys.modules:
        pytest.skip("_posixsubprocess not loaded")
    install(trace=False)
    try:
        import _posixsubprocess

        with pytest.raises(PolicyViolation, match="subprocess"):
            # Doesn't matter what args — call should be intercepted.
            _posixsubprocess.fork_exec(
                [b"/bin/true"], [b"/bin/true"], True, (), None, None,
                -1, -1, -1, -1, -1, -1, -1, -1, False, False, None,
                None, None, -1, None, False,
            )
    finally:
        uninstall()


def test_subprocess_check_call_blocked():
    install(trace=False)
    try:
        import subprocess

        with pytest.raises(PolicyViolation, match="subprocess"):
            subprocess.check_call(["whatever"])
    finally:
        uninstall()
