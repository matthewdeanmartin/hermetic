"""Tests for BlockConfig.merged_with, _effective_config, profiles, and sealed mode."""

from __future__ import annotations

import pytest

import hermetic.blocker as blocker_mod
from hermetic.blocker import BlockConfig, _effective_config, hermetic_blocker
from hermetic.profiles import PROFILES, GuardConfig, apply_profile

# ============================================================================
# BlockConfig.merged_with
# ============================================================================


class TestBlockConfigMergedWith:
    """Verify the strict-wins merge logic."""

    def test_bool_fields_or_together(self):
        a = BlockConfig(block_network=True, block_subprocess=False)
        b = BlockConfig(block_network=False, block_subprocess=True)
        m = a.merged_with(b)
        assert m.block_network is True
        assert m.block_subprocess is True

    def test_all_bool_fields_propagate(self):
        full = BlockConfig(
            block_network=True,
            block_subprocess=True,
            fs_readonly=True,
            block_environment=True,
            block_code_exec=True,
            block_interpreter_mutation=True,
            block_native=True,
            allow_localhost=True,
            trace=True,
            sealed=True,
        )
        empty = BlockConfig()
        m = empty.merged_with(full)
        assert m.block_network is True
        assert m.block_subprocess is True
        assert m.fs_readonly is True
        assert m.block_environment is True
        assert m.block_code_exec is True
        assert m.block_interpreter_mutation is True
        assert m.block_native is True
        assert m.allow_localhost is True
        assert m.trace is True
        assert m.sealed is True

    def test_fs_root_other_wins(self):
        a = BlockConfig(fs_root="/old")
        b = BlockConfig(fs_root="/new")
        m = a.merged_with(b)
        assert m.fs_root == "/new"

    def test_fs_root_fallback_to_self(self):
        a = BlockConfig(fs_root="/base")
        b = BlockConfig(fs_root=None)
        m = a.merged_with(b)
        assert m.fs_root == "/base"

    def test_allow_domains_deduplicated(self):
        a = BlockConfig(allow_domains=["x.com", "y.com"])
        b = BlockConfig(allow_domains=["y.com", "z.com"])
        m = a.merged_with(b)
        assert m.allow_domains == ["x.com", "y.com", "z.com"]

    def test_deny_imports_deduplicated(self):
        a = BlockConfig(deny_imports=["pickle", "marshal"])
        b = BlockConfig(deny_imports=["marshal", "shelve"])
        m = a.merged_with(b)
        assert m.deny_imports == ["pickle", "marshal", "shelve"]

    def test_symmetric_empty_merge(self):
        a = BlockConfig()
        b = BlockConfig()
        assert a.merged_with(b) == BlockConfig()

    def test_merge_is_not_mutation(self):
        a = BlockConfig(block_network=True)
        b = BlockConfig(block_subprocess=True)
        _ = a.merged_with(b)
        # originals unchanged
        assert a.block_subprocess is False
        assert b.block_network is False


# ============================================================================
# _effective_config
# ============================================================================


class TestEffectiveConfig:
    """Verify _effective_config merges the active stack correctly."""

    def setup_method(self):
        blocker_mod._ACTIVE_CONFIGS.clear()

    def teardown_method(self):
        blocker_mod._ACTIVE_CONFIGS.clear()

    def test_empty_stack_returns_defaults(self):
        cfg = _effective_config()
        assert cfg == BlockConfig()

    def test_single_config_returned_as_is(self):
        blocker_mod._ACTIVE_CONFIGS.append(BlockConfig(block_network=True))
        assert _effective_config().block_network is True

    def test_two_configs_merged(self):
        blocker_mod._ACTIVE_CONFIGS.append(BlockConfig(block_network=True))
        blocker_mod._ACTIVE_CONFIGS.append(BlockConfig(block_subprocess=True))
        cfg = _effective_config()
        assert cfg.block_network is True
        assert cfg.block_subprocess is True

    def test_deny_imports_accumulated(self):
        blocker_mod._ACTIVE_CONFIGS.append(BlockConfig(deny_imports=["pickle"]))
        blocker_mod._ACTIVE_CONFIGS.append(BlockConfig(deny_imports=["marshal"]))
        cfg = _effective_config()
        assert "pickle" in cfg.deny_imports
        assert "marshal" in cfg.deny_imports


# ============================================================================
# Profiles
# ============================================================================


class TestProfiles:
    """Verify all named profiles have the expected guard flags."""

    def test_block_all_profile_enables_everything(self):
        cfg = apply_profile(GuardConfig(), "block-all")
        assert cfg.block_native is True
        assert cfg.no_subprocess is True
        assert cfg.no_network is True
        assert cfg.fs_readonly is True
        assert cfg.no_environment is True
        assert cfg.no_code_exec is True
        assert cfg.no_interpreter_mutation is True

    def test_net_hermetic_profile(self):
        cfg = apply_profile(GuardConfig(), "net-hermetic")
        assert cfg.no_network is True
        assert cfg.allow_localhost is True
        assert cfg.no_subprocess is False

    def test_exec_deny_profile(self):
        cfg = apply_profile(GuardConfig(), "exec-deny")
        assert cfg.no_subprocess is True
        assert cfg.no_network is False

    def test_fs_readonly_profile(self):
        cfg = apply_profile(GuardConfig(), "fs-readonly")
        assert cfg.fs_readonly is True

    def test_block_native_profile(self):
        cfg = apply_profile(GuardConfig(), "block-native")
        assert cfg.block_native is True

    def test_unknown_profile_raises_system_exit(self):
        with pytest.raises(SystemExit, match="unknown profile"):
            apply_profile(GuardConfig(), "does-not-exist")

    def test_profiles_dict_contains_expected_keys(self):
        assert set(PROFILES.keys()) == {
            "block-all",
            "net-hermetic",
            "exec-deny",
            "fs-readonly",
            "block-native",
        }

    def test_apply_profile_does_not_mutate_base(self):
        base = GuardConfig()
        apply_profile(base, "block-all")
        assert base.no_network is False  # base unchanged

    def test_apply_profile_stacks(self):
        cfg = apply_profile(GuardConfig(), "net-hermetic")
        cfg = apply_profile(cfg, "exec-deny")
        assert cfg.no_network is True
        assert cfg.no_subprocess is True

    def test_apply_profile_list_fields_extend(self):
        base = GuardConfig(allow_domains=["a.example"])
        cfg = apply_profile(base, "net-hermetic")
        # no_network=True set; allow_domains list unchanged because profile has none
        assert cfg.no_network is True
        assert "a.example" in cfg.allow_domains

    def test_apply_profile_str_field_set(self):
        # Create a custom base with no fs_root, apply block-all (no fs_root either)
        # Just verify the merge path for str fields doesn't crash
        base = GuardConfig(fs_root="/base")
        cfg = apply_profile(base, "fs-readonly")
        assert cfg.fs_root == "/base"  # block-all doesn't set fs_root, base survives


# ============================================================================
# BlockConfig.from_kwargs — alias coverage
# ============================================================================


class TestFromKwargsAliases:
    """Ensure all documented aliases round-trip correctly."""

    def test_no_env_alias(self):
        cfg = BlockConfig.from_kwargs(no_env=True)
        assert cfg.block_environment is True

    def test_no_environment_alias(self):
        cfg = BlockConfig.from_kwargs(no_environment=True)
        assert cfg.block_environment is True

    def test_block_environment_direct(self):
        cfg = BlockConfig.from_kwargs(block_environment=True)
        assert cfg.block_environment is True

    def test_no_code_exec_alias(self):
        cfg = BlockConfig.from_kwargs(no_code_exec=True)
        assert cfg.block_code_exec is True

    def test_no_interpreter_mutation_alias(self):
        cfg = BlockConfig.from_kwargs(no_interpreter_mutation=True)
        assert cfg.block_interpreter_mutation is True

    def test_fs_root_passed_through(self):
        cfg = BlockConfig.from_kwargs(fs_root="/sandbox")
        assert cfg.fs_root == "/sandbox"

    def test_deny_imports_passed_through(self):
        cfg = BlockConfig.from_kwargs(deny_imports=["pickle", "marshal"])
        assert cfg.deny_imports == ["pickle", "marshal"]

    def test_sealed_passed_through(self):
        cfg = BlockConfig.from_kwargs(sealed=True)
        assert cfg.sealed is True


# ============================================================================
# Sealed mode (stubbed guards — no real installation needed)
# ============================================================================


class TestSealedMode:
    """Verify _SEALED latch and its effect on _reapply_guards_locked."""

    def setup_method(self):
        # Reset global state before each test
        blocker_mod._ACTIVE_CONFIGS.clear()
        blocker_mod._SEALED = False

    def teardown_method(self):
        blocker_mod._ACTIVE_CONFIGS.clear()
        blocker_mod._SEALED = False

    def test_sealed_flag_is_set_on_enter(self, monkeypatch):
        monkeypatch.setattr(blocker_mod, "install_all", lambda **k: None)
        monkeypatch.setattr(blocker_mod, "uninstall_all", lambda: None)

        b = hermetic_blocker(sealed=True)
        b.__enter__()
        assert blocker_mod._SEALED is True
        b.__exit__(None, None, None)

    def test_sealed_persists_after_exit(self, monkeypatch):
        monkeypatch.setattr(blocker_mod, "install_all", lambda **k: None)
        monkeypatch.setattr(blocker_mod, "uninstall_all", lambda: None)

        with hermetic_blocker(sealed=True):
            pass
        # latch is never reset
        assert blocker_mod._SEALED is True

    def test_sealed_mode_skips_uninstall(self, monkeypatch):
        uninstall_calls = []
        monkeypatch.setattr(blocker_mod, "install_all", lambda **k: None)
        monkeypatch.setattr(
            blocker_mod, "uninstall_all", lambda: uninstall_calls.append(1)
        )
        blocker_mod._SEALED = True

        from hermetic.blocker import _reapply_guards_locked

        blocker_mod._ACTIVE_CONFIGS.append(BlockConfig(block_network=True))
        _reapply_guards_locked()
        # uninstall_all should NOT have been called in sealed mode
        assert len(uninstall_calls) == 0

    def test_reapply_sealed_with_empty_stack_does_nothing(self, monkeypatch):
        install_calls = []
        monkeypatch.setattr(
            blocker_mod, "install_all", lambda **k: install_calls.append(1)
        )
        monkeypatch.setattr(blocker_mod, "uninstall_all", lambda: None)
        blocker_mod._SEALED = True

        from hermetic.blocker import _reapply_guards_locked

        # Empty stack + sealed → no install, no uninstall
        _reapply_guards_locked()
        assert len(install_calls) == 0
