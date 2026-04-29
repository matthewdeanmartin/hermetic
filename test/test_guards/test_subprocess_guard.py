# tests/test_guards/test_subprocess_guard.py
import subprocess
import sys

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.subprocess_guard import install, uninstall


def test_subprocess_guard():
    install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="subprocess disabled"):
            subprocess.run(["echo", "test"])
    finally:
        uninstall()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only primitive")
def test_winapi_create_process_blocked():
    import _winapi

    install()
    try:
        with pytest.raises(PolicyViolation, match="subprocess disabled"):
            _winapi.CreateProcess(
                None, "cmd.exe /c echo hi", None, None, False, 0, None, None, None
            )
    finally:
        uninstall()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only primitive")
def test_posix_fork_exec_blocked():
    import _posixsubprocess

    install()
    try:
        with pytest.raises(PolicyViolation, match="subprocess disabled"):
            _posixsubprocess.fork_exec()
    finally:
        uninstall()
