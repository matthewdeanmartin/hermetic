# tests/conftest.py
import pytest

from hermetic.blocker import BlockConfig
from hermetic.profiles import GuardConfig


@pytest.fixture
def default_block_config():
    return BlockConfig(
        block_network=False,
        block_subprocess=False,
        fs_readonly=False,
        fs_root=None,
        block_environment=False,
        block_code_exec=False,
        block_interpreter_mutation=False,
        block_native=False,
        allow_localhost=False,
        allow_domains=[],
        deny_imports=[],
        trace=False,
    )


@pytest.fixture
def default_guard_config():
    return GuardConfig(
        no_network=False,
        no_subprocess=False,
        fs_readonly=False,
        fs_root=None,
        no_environment=False,
        no_code_exec=False,
        no_interpreter_mutation=False,
        block_native=False,
        allow_localhost=False,
        allow_domains=[],
        deny_imports=[],
        trace=False,
    )
