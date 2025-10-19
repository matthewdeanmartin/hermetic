# tests/test_guards/test_subprocess_guard.py
import pytest
import subprocess
from hermetic.guards.subprocess_guard import install, uninstall
from hermetic.errors import PolicyViolation

def test_subprocess_guard():
    install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="subprocess disabled"):
            subprocess.run(["echo", "test"])
    finally:
        uninstall()