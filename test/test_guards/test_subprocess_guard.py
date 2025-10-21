# tests/test_guards/test_subprocess_guard.py
import subprocess

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
