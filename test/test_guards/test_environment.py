import os

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.environment import install, uninstall


def test_environment_guard_blocks_reads_and_writes():
    install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="environment disabled"):
            os.getenv("PATH")

        with pytest.raises(PolicyViolation, match="environment disabled"):
            os.environ["PATH"]

        with pytest.raises(PolicyViolation, match="environment mutation disabled"):
            os.putenv("HERMETIC_TEST", "1")
    finally:
        uninstall()
