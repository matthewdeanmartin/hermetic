# tests/test_runner.py
import pytest
from hermetic.runner import config_to_flags, run
from hermetic.profiles import GuardConfig
from hermetic.resolver import TargetSpec

def test_config_to_flags(default_guard_config):
    cfg = GuardConfig(no_network=True, allow_domains=["example.com"], trace=True)
    flags = config_to_flags(cfg)
    assert flags == {
        "no_network": True,
        "no_subprocess": False,
        "fs_readonly": False,
        "fs_root": None,
        "strict_imports": False,
        "allow_localhost": False,
        "allow_domains": ["example.com"],
        "trace": True
    }

def test_run_inprocess(mocker):
    # Mock invoke_inprocess to avoid actual module execution
    mocker.patch("hermetic.runner.invoke_inprocess", return_value=0)
    cfg = GuardConfig(no_network=True)
    exit_code = run("mymodule", ["mymodule", "--arg"], cfg)
    assert exit_code == 0