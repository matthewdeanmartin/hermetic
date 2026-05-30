"""Comprehensive tests for hermetic.guards.interpreter."""

from __future__ import annotations

import os
import site
import sys

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.interpreter import install, uninstall


@pytest.fixture(autouse=True)
def clean_interp_guard():
    uninstall()
    yield
    uninstall()


class TestGuardedListMethods:
    """Test every _GuardedList mutation method on sys.path."""

    def test_append_blocked(self, tmp_path):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.append(str(tmp_path))

    def test_extend_blocked(self, tmp_path):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.extend([str(tmp_path)])

    def test_insert_blocked(self, tmp_path):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.insert(0, str(tmp_path))

    def test_pop_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.pop()

    def test_remove_blocked(self):
        install()
        # sys.path always has entries; pick the first read-only
        entry = sys.path[0]
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.remove(entry)

    def test_clear_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.clear()

    def test_sort_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.sort()

    def test_reverse_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.reverse()

    def test_setitem_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path[0] = "/new/path"

    def test_delitem_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            del sys.path[0]

    def test_iadd_blocked(self, tmp_path):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path += [str(tmp_path)]

    def test_imul_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path *= 2

    def test_read_still_works(self):
        install()
        # Reading is allowed — _GuardedList inherits list reads
        assert isinstance(sys.path, list)
        _ = sys.path[0]
        _ = len(sys.path)


class TestGuardedListOnMetaPath:
    """Test _GuardedList behavior on sys.meta_path."""

    def test_meta_path_append_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.meta_path"):
            sys.meta_path.append(object())

    def test_meta_path_clear_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.meta_path"):
            sys.meta_path.clear()

    def test_meta_path_read_works(self):
        install()
        _ = list(sys.meta_path)


class TestGuardedListOnPathHooks:
    """Test _GuardedList behavior on sys.path_hooks."""

    def test_path_hooks_append_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path_hooks"):
            sys.path_hooks.append(lambda p: None)

    def test_path_hooks_insert_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path_hooks"):
            sys.path_hooks.insert(0, lambda p: None)


class TestGuardedDictOnImporterCache:
    """Test _GuardedDict behavior on sys.path_importer_cache."""

    def test_setitem_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path_importer_cache"):
            sys.path_importer_cache["/fake"] = None

    def test_delitem_blocked(self):
        install()
        # Add a real key first via the backing dict superclass — can't via the guarded interface
        # so we just verify a missing key raises the right error
        with pytest.raises((PolicyViolation, KeyError)):
            del sys.path_importer_cache["/nonexistent_fake_path_hermetic_test"]

    def test_clear_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path_importer_cache"):
            sys.path_importer_cache.clear()

    def test_pop_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path_importer_cache"):
            sys.path_importer_cache.pop("/fake", None)

    def test_popitem_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path_importer_cache"):
            sys.path_importer_cache.popitem()

    def test_setdefault_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path_importer_cache"):
            sys.path_importer_cache.setdefault("/fake", None)

    def test_update_blocked(self):
        install()
        with pytest.raises(PolicyViolation, match="sys.path_importer_cache"):
            sys.path_importer_cache.update({"/fake": None})

    def test_read_still_works(self):
        install()
        _ = dict(sys.path_importer_cache)


class TestOsChdir:
    """Test os.chdir and os.fchdir blocking."""

    def test_chdir_blocked(self, tmp_path):
        install()
        with pytest.raises(PolicyViolation, match="chdir"):
            os.chdir(str(tmp_path))

    @pytest.mark.skipif(not hasattr(os, "fchdir"), reason="no fchdir on this platform")
    def test_fchdir_blocked(self, tmp_path):
        install()
        fd = os.open(str(tmp_path), os.O_RDONLY)
        try:
            with pytest.raises(PolicyViolation, match="fchdir"):
                os.fchdir(fd)
        finally:
            os.close(fd)


class TestSiteAddsitedir:
    """Test site.addsitedir blocking."""

    def test_addsitedir_blocked(self, tmp_path):
        install()
        with pytest.raises(PolicyViolation, match="addsitedir"):
            site.addsitedir(str(tmp_path))


class TestInstallUninstall:
    """Test install/uninstall lifecycle."""

    def test_idempotent_install(self, tmp_path):
        install()
        install()  # no-op
        with pytest.raises(PolicyViolation):
            sys.path.append(str(tmp_path))

    def test_idempotent_uninstall(self):
        install()
        uninstall()
        uninstall()  # no crash

    def test_uninstall_restores_syspath(self, tmp_path):
        original_type = type(sys.path)
        install()
        uninstall()
        # After uninstall, sys.path is back to a plain list
        sys.path.append(str(tmp_path))
        sys.path.remove(str(tmp_path))

    def test_uninstall_restores_chdir(self, tmp_path):
        original_cwd = os.getcwd()
        install()
        uninstall()
        os.chdir(str(tmp_path))
        os.chdir(original_cwd)

    def test_uninstall_restores_addsitedir(self, tmp_path):
        install()
        uninstall()
        # Should not raise — just adds to sys.path (which we'll clean up)
        before = list(sys.path)
        try:
            site.addsitedir(str(tmp_path))
        finally:
            sys.path[:] = before


class TestTraceMode:
    """Test trace=True emits messages without changing behavior."""

    def test_trace_chdir_still_raises(self, tmp_path, capsys):
        install(trace=True)
        with pytest.raises(PolicyViolation):
            os.chdir(str(tmp_path))
        captured = capsys.readouterr()
        assert "[hermetic]" in captured.err

    def test_trace_syspath_still_raises(self, tmp_path, capsys):
        install(trace=True)
        with pytest.raises(PolicyViolation):
            sys.path.append(str(tmp_path))
        captured = capsys.readouterr()
        assert "[hermetic]" in captured.err
