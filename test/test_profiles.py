# tests/test_profiles.py
import pytest
from hermetic.profiles import GuardConfig, apply_profile, PROFILES

def test_guard_config_defaults(default_guard_config):
    assert default_guard_config == GuardConfig()

def test_apply_profile():
    base = GuardConfig()
    cfg = apply_profile(base, "net-hermetic")
    assert cfg.no_network is True
    assert cfg.allow_localhost is True
    assert cfg.no_subprocess is False

    cfg = apply_profile(cfg, "exec-deny")
    assert cfg.no_network is True
    assert cfg.no_subprocess is True

    with pytest.raises(SystemExit, match="unknown profile: invalid"):
        apply_profile(base, "invalid")