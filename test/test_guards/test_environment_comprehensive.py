"""Comprehensive tests for hermetic.guards.environment."""

from __future__ import annotations

import os

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.environment import install, uninstall


# Each test installs and uninstalls within a try/finally so that pytest's own
# teardown machinery (which reads os.environ for terminal/color settings) never
# runs while the guard is active.


class TestGuardedEnvironMapping:
    """Test every _GuardedEnviron method that should raise."""

    def test_getitem_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                _ = os.environ["PATH"]
        finally:
            uninstall()

    def test_setitem_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.environ["NEW_VAR"] = "value"
        finally:
            uninstall()

    def test_delitem_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                del os.environ["PATH"]
        finally:
            uninstall()

    def test_iter_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                list(os.environ)
        finally:
            uninstall()

    def test_len_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                len(os.environ)
        finally:
            uninstall()

    def test_get_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                os.environ.get("PATH")
        finally:
            uninstall()

    def test_get_with_default_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                os.environ.get("PATH", "fallback")
        finally:
            uninstall()

    def test_copy_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                os.environ.copy()
        finally:
            uninstall()

    def test_items_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                os.environ.items()
        finally:
            uninstall()

    def test_keys_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                os.environ.keys()
        finally:
            uninstall()

    def test_values_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                os.environ.values()
        finally:
            uninstall()

    def test_contains_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                _ = "PATH" in os.environ
        finally:
            uninstall()

    def test_pop_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.environ.pop("PATH")
        finally:
            uninstall()

    def test_popitem_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.environ.popitem()
        finally:
            uninstall()

    def test_clear_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.environ.clear()
        finally:
            uninstall()

    def test_setdefault_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.environ.setdefault("KEY", "val")
        finally:
            uninstall()

    def test_update_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.environ.update({"KEY": "val"})
        finally:
            uninstall()

    def test_update_kwargs_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.environ.update(KEY="val")
        finally:
            uninstall()

    def test_repr_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                repr(os.environ)
        finally:
            uninstall()


class TestStandaloneFunctions:
    """Test os.getenv, os.putenv, os.unsetenv blocking."""

    def test_getenv_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                os.getenv("PATH")
        finally:
            uninstall()

    def test_getenv_with_default_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment disabled"):
                os.getenv("PATH", "default")
        finally:
            uninstall()

    def test_putenv_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.putenv("HERMETIC_TEST", "1")
        finally:
            uninstall()

    def test_unsetenv_raises(self):
        install()
        try:
            with pytest.raises(PolicyViolation, match="environment mutation disabled"):
                os.unsetenv("HERMETIC_TEST")
        finally:
            uninstall()


class TestInstallUninstall:
    """Test install/uninstall lifecycle."""

    def test_idempotent_install(self):
        install()
        install()  # second call is a no-op
        try:
            with pytest.raises(PolicyViolation):
                os.getenv("PATH")
        finally:
            uninstall()

    def test_idempotent_uninstall(self):
        install()
        uninstall()
        uninstall()  # no crash
        os.getenv("PATH")  # should work normally

    def test_uninstall_restores_getenv(self):
        original = os.getenv("PATH")
        install()
        uninstall()
        assert os.getenv("PATH") == original

    def test_uninstall_restores_environ_get(self):
        install()
        uninstall()
        _ = os.environ.get("PATH")  # should not raise

    def test_uninstall_restores_putenv(self):
        install()
        uninstall()
        os.putenv("HERMETIC_GUARD_TEST", "1")
        os.unsetenv("HERMETIC_GUARD_TEST")


class TestTraceMode:
    """Test trace=True emits messages without changing behavior."""

    def test_trace_read_still_raises(self, capsys):
        install(trace=True)
        try:
            with pytest.raises(PolicyViolation):
                os.getenv("PATH")
        finally:
            uninstall()
        captured = capsys.readouterr()
        assert "[hermetic]" in captured.err

    def test_trace_write_still_raises(self, capsys):
        install(trace=True)
        try:
            with pytest.raises(PolicyViolation):
                os.environ["K"] = "V"
        finally:
            uninstall()
        captured = capsys.readouterr()
        assert "[hermetic]" in captured.err
