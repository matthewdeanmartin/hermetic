import os
import site
import sys

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.interpreter import install, uninstall


def test_interpreter_guard_blocks_mutation(tmp_path):
    install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.append(str(tmp_path))

        with pytest.raises(PolicyViolation, match="chdir"):
            os.chdir(str(tmp_path))

        with pytest.raises(PolicyViolation, match="addsitedir"):
            site.addsitedir(str(tmp_path))
    finally:
        uninstall()
