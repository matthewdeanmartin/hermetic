# tests/conftest.py
import pytest
from hermetic.profiles import GuardConfig
from hermetic.blocker import BlockConfig

@pytest.fixture
def default_block_config():
    return BlockConfig(
        block_network=False,
        block_subprocess=False,
        fs_readonly=False,
        fs_root=None,
        strict_imports=False,
        allow_localhost=False,
        allow_domains=[],
        trace=False
    )

@pytest.fixture
def default_guard_config():
    return GuardConfig(
        no_network=False,
        no_subprocess=False,
        fs_readonly=False,
        fs_root=None,
        strict_imports=False,
        allow_localhost=False,
        allow_domains=[],
        trace=False
    )