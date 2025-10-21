# tests/test_blocker.py

import pytest

from hermetic.blocker import _REFCOUNT, BlockConfig, hermetic_blocker


def test_block_config_from_kwargs(default_block_config):
    cfg = BlockConfig.from_kwargs(block_network=True, allow_localhost=True)
    assert cfg.block_network is True
    assert cfg.allow_localhost is True
    assert cfg == BlockConfig(block_network=True, allow_localhost=True)

    cfg = BlockConfig.from_kwargs(no_network=True, no_subprocess=True)
    assert cfg.block_network is True
    assert cfg.block_subprocess is True

    with pytest.raises(TypeError, match="Unknown argument: invalid"):
        BlockConfig.from_kwargs(invalid=True)


# def test_hermetic_blocker_context_manager(default_block_config):
#     global _REFCOUNT
#     initial_refcount = _REFCOUNT
#     with hermetic_blocker(block_network=True) as blocker:
#         assert isinstance(blocker, _HermeticBlocker)
#         assert _REFCOUNT == initial_refcount + 1
#         assert blocker.cfg == BlockConfig(block_network=True)
#     assert _REFCOUNT == initial_refcount

# def test_hermetic_blocker_nested():
#     global _REFCOUNT
#     initial_refcount = _REFCOUNT
#     with hermetic_blocker(block_network=True):
#         assert _REFCOUNT == initial_refcount + 1
#         with hermetic_blocker(block_subprocess=True):
#             assert _REFCOUNT == initial_refcount + 2
#         assert _REFCOUNT == initial_refcount + 1
#     assert _REFCOUNT == initial_refcount

# @pytest.mark.asyncio
# async def test_hermetic_blocker_async():
#     global _REFCOUNT
#     initial_refcount = _REFCOUNT
#     async with hermetic_blocker(block_network=True) as blocker:
#         assert isinstance(blocker, _HermeticBlocker)
#         assert _REFCOUNT == initial_refcount + 1
#     assert _REFCOUNT == initial_refcount


def test_with_hermetic_decorator():
    @hermetic_blocker(block_network=True)
    def test_func():
        return True

    global _REFCOUNT
    initial_refcount = _REFCOUNT
    assert test_func() is True
    assert _REFCOUNT == initial_refcount
