"""Tests for the 5 API ergonomics improvements in 1.0.0."""

from __future__ import annotations

import socket

import pytest

import hermetic.blocker as blocker_mod
from hermetic.blocker import BlockConfig, hermetic_blocker, with_hermetic
from hermetic.errors import PolicyViolation
from hermetic.profiles import GuardConfig

# ============================================================================
# 1. PolicyViolation.guard and .target attributes
# ============================================================================


class TestPolicyViolationAttributes:
    """guard and target attributes on PolicyViolation."""

    def test_guard_attribute_set(self):
        exc = PolicyViolation("network disabled: DNS(x)", guard="network", target="x")
        assert exc.guard == "network"
        assert exc.target == "x"

    def test_guard_defaults_to_none(self):
        exc = PolicyViolation("something blocked")
        assert exc.guard is None
        assert exc.target is None

    def test_network_guard_raises_with_guard_attr(self):
        with hermetic_blocker(block_network=True):
            try:
                socket.getaddrinfo("example.com", 80)
            except PolicyViolation as e:
                assert e.guard == "network"
                assert e.target == "example.com"
            else:
                pytest.fail("Expected PolicyViolation")

    def test_subprocess_guard_raises_with_guard_attr(self):
        with hermetic_blocker(block_subprocess=True):
            import subprocess

            try:
                subprocess.run(["echo", "hi"])
            except PolicyViolation as e:
                assert e.guard == "subprocess"
            else:
                pytest.fail("Expected PolicyViolation")

    def test_filesystem_guard_raises_with_guard_attr(self, tmp_path):
        test_file = tmp_path / "f.txt"
        with hermetic_blocker(fs_readonly=True):
            try:
                open(test_file, "w")
            except PolicyViolation as e:
                assert e.guard == "filesystem"
                assert e.target is not None
            else:
                pytest.fail("Expected PolicyViolation")

    def test_environment_guard_raises_with_guard_attr(self):
        import os

        with hermetic_blocker(block_environment=True):
            try:
                os.environ["PATH"]
            except PolicyViolation as e:
                assert e.guard == "environment"
            else:
                pytest.fail("Expected PolicyViolation")

    def test_imports_guard_raises_with_guard_attr(self):
        with hermetic_blocker(block_native=True):
            try:
                import ctypes  # noqa: F401
            except PolicyViolation as e:
                assert e.guard == "imports"
                assert e.target is not None
            else:
                pytest.fail("Expected PolicyViolation")

    def test_code_exec_guard_raises_with_guard_attr(self):
        with hermetic_blocker(block_code_exec=True):
            try:
                eval("1+1")  # noqa: S307
            except PolicyViolation as e:
                assert e.guard == "code_exec"
                assert e.target == "eval"
            else:
                pytest.fail("Expected PolicyViolation")

    def test_interpreter_guard_raises_with_guard_attr(self, tmp_path):
        import sys

        with hermetic_blocker(block_interpreter_mutation=True):
            try:
                sys.path.append(str(tmp_path))
            except PolicyViolation as e:
                assert e.guard == "interpreter"
                assert e.target == "sys.path"
            else:
                pytest.fail("Expected PolicyViolation")

    def test_is_still_exception(self):
        exc = PolicyViolation("bad", guard="network")
        assert isinstance(exc, Exception)
        assert str(exc) == "bad"

    def test_guard_attr_catchable_by_name(self):
        violations = []
        with hermetic_blocker(block_network=True):
            try:
                socket.getaddrinfo("example.com", 80)
            except PolicyViolation as e:
                violations.append(e.guard)
        assert violations == ["network"]


# ============================================================================
# 2. BlockConfig.__or__ operator
# ============================================================================


class TestBlockConfigOrOperator:
    """BlockConfig | BlockConfig == merged_with."""

    def test_or_is_alias_for_merged_with(self):
        a = BlockConfig(block_network=True)
        b = BlockConfig(block_subprocess=True)
        assert (a | b) == a.merged_with(b)

    def test_or_returns_new_instance(self):
        a = BlockConfig(block_network=True)
        b = BlockConfig(block_subprocess=True)
        c = a | b
        assert c is not a
        assert c is not b

    def test_or_does_not_mutate_operands(self):
        a = BlockConfig(block_network=True)
        b = BlockConfig(block_subprocess=True)
        _ = a | b
        assert a.block_subprocess is False
        assert b.block_network is False

    def test_or_chains(self):
        a = BlockConfig(block_network=True)
        b = BlockConfig(block_subprocess=True)
        c = BlockConfig(fs_readonly=True)
        result = a | b | c
        assert result.block_network is True
        assert result.block_subprocess is True
        assert result.fs_readonly is True

    def test_or_merges_allow_domains(self):
        a = BlockConfig(block_network=True, allow_domains=["a.example"])
        b = BlockConfig(block_network=True, allow_domains=["b.example"])
        merged = a | b
        assert "a.example" in merged.allow_domains
        assert "b.example" in merged.allow_domains

    def test_or_merges_deny_imports(self):
        a = BlockConfig(deny_imports=["pickle"])
        b = BlockConfig(deny_imports=["marshal"])
        merged = a | b
        assert "pickle" in merged.deny_imports
        assert "marshal" in merged.deny_imports

    def test_or_with_empty_right(self):
        a = BlockConfig(block_network=True)
        result = a | BlockConfig()
        assert result.block_network is True

    def test_or_identity_empty(self):
        a = BlockConfig()
        assert (a | BlockConfig()) == BlockConfig()

    def test_or_used_with_hermetic_blocker(self, monkeypatch):
        calls = []
        monkeypatch.setattr(blocker_mod, "install_all", lambda **k: calls.append(k))
        monkeypatch.setattr(blocker_mod, "uninstall_all", lambda: None)
        blocker_mod._ACTIVE_CONFIGS.clear()

        net = BlockConfig(block_network=True)
        sub = BlockConfig(block_subprocess=True)
        with hermetic_blocker(net | sub):
            pass
        assert calls[0]["net"] is not None
        assert calls[0]["subproc"] is not None

        blocker_mod._ACTIVE_CONFIGS.clear()


# ============================================================================
# 3. Unified naming — GuardConfig.block_* aliases
# ============================================================================


class TestGuardConfigBlockAliases:
    """GuardConfig exposes block_* properties alongside no_* fields."""

    def test_block_network_alias(self):
        cfg = GuardConfig(no_network=True)
        assert cfg.block_network is True

    def test_block_subprocess_alias(self):
        cfg = GuardConfig(no_subprocess=True)
        assert cfg.block_subprocess is True

    def test_block_environment_alias(self):
        cfg = GuardConfig(no_environment=True)
        assert cfg.block_environment is True

    def test_block_code_exec_alias(self):
        cfg = GuardConfig(no_code_exec=True)
        assert cfg.block_code_exec is True

    def test_block_interpreter_mutation_alias(self):
        cfg = GuardConfig(no_interpreter_mutation=True)
        assert cfg.block_interpreter_mutation is True

    def test_false_by_default(self):
        cfg = GuardConfig()
        assert cfg.block_network is False
        assert cfg.block_subprocess is False
        assert cfg.block_environment is False
        assert cfg.block_code_exec is False
        assert cfg.block_interpreter_mutation is False

    def test_block_native_is_direct_field(self):
        cfg = GuardConfig(block_native=True)
        assert cfg.block_native is True


# ============================================================================
# 4. hermetic_blocker accepts a BlockConfig directly
# ============================================================================


class TestHermeticBlockerAcceptsBlockConfig:
    """hermetic_blocker(cfg) where cfg is a BlockConfig."""

    def test_positional_blockconfig_accepted(self, monkeypatch):
        calls = []
        monkeypatch.setattr(blocker_mod, "install_all", lambda **k: calls.append(k))
        monkeypatch.setattr(blocker_mod, "uninstall_all", lambda: None)
        blocker_mod._ACTIVE_CONFIGS.clear()

        cfg = BlockConfig(block_network=True)
        with hermetic_blocker(cfg):
            pass
        assert calls[0]["net"] is not None

        blocker_mod._ACTIVE_CONFIGS.clear()

    def test_positional_blockconfig_blocks_network(self):
        cfg = BlockConfig(block_network=True)
        with hermetic_blocker(cfg):
            with pytest.raises(PolicyViolation, match="network disabled"):
                socket.getaddrinfo("example.com", 80)

    def test_positional_blockconfig_wrong_type_raises(self):
        with pytest.raises(TypeError, match="BlockConfig"):
            hermetic_blocker("net-hermetic")  # type: ignore[arg-type]

    def test_with_hermetic_accepts_blockconfig(self):
        cfg = BlockConfig(block_network=True)
        with with_hermetic(cfg):
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)

    def test_positional_blockconfig_as_decorator(self):
        cfg = BlockConfig(block_network=True)

        @hermetic_blocker(cfg)
        def fn():
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)

        fn()

    def test_prebuilt_config_reuse(self):
        cfg = BlockConfig(block_network=True)
        for _ in range(3):
            with hermetic_blocker(cfg):
                with pytest.raises(PolicyViolation):
                    socket.getaddrinfo("example.com", 80)


# ============================================================================
# 5. profile= kwarg on hermetic_blocker
# ============================================================================


class TestHermeticBlockerProfileKwarg:
    """hermetic_blocker(profile="name") applies the named profile."""

    def test_profile_net_hermetic_blocks_network(self):
        with hermetic_blocker(profile="net-hermetic"):
            with pytest.raises(PolicyViolation, match="network disabled"):
                socket.getaddrinfo("example.com", 80)

    def test_profile_net_hermetic_allows_localhost(self):
        with hermetic_blocker(profile="net-hermetic"):
            info = socket.getaddrinfo("localhost", 80)
            assert len(info) > 0

    def test_profile_exec_deny_blocks_subprocess(self):
        with hermetic_blocker(profile="exec-deny"):
            import subprocess

            with pytest.raises(PolicyViolation, match="subprocess disabled"):
                subprocess.run(["echo", "hi"])

    def test_profile_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown hermetic profile"):
            hermetic_blocker(profile="does-not-exist")

    def test_profile_merges_with_kwargs(self):
        with hermetic_blocker(block_subprocess=True, profile="net-hermetic"):
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)
            import subprocess

            with pytest.raises(PolicyViolation):
                subprocess.run(["echo", "hi"])

    def test_profile_merges_with_blockconfig(self, monkeypatch):
        calls = []
        monkeypatch.setattr(blocker_mod, "install_all", lambda **k: calls.append(k))
        monkeypatch.setattr(blocker_mod, "uninstall_all", lambda: None)
        blocker_mod._ACTIVE_CONFIGS.clear()

        cfg = BlockConfig(block_subprocess=True)
        with hermetic_blocker(cfg, profile="net-hermetic"):
            pass
        assert calls[0]["net"] is not None
        assert calls[0]["subproc"] is not None

        blocker_mod._ACTIVE_CONFIGS.clear()

    def test_profile_block_all_enables_all_guards(self, tmp_path):
        test_file = tmp_path / "f.txt"
        with hermetic_blocker(profile="block-all"):
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)
            with pytest.raises(PolicyViolation):
                open(test_file, "w")
