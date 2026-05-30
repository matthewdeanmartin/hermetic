"""Phase 3 hardening tests: _posixsubprocess and shutil-style entry points."""

from __future__ import annotations

import os
import sys

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.subprocess_guard import install, uninstall


def test_posix_spawn_blocked():
    if not hasattr(os, "posix_spawn"):
        pytest.skip("os.posix_spawn not available on this platform")
    install(trace=False)
    try:
        with pytest.raises(PolicyViolation, match="subprocess"):
            os.posix_spawn("/bin/true", ["/bin/true"], os.environ)
    finally:
        uninstall()


def test_posixsubprocess_blocked():
    if "_posixsubprocess" not in sys.modules:
        pytest.skip("_posixsubprocess not loaded")
    install(trace=False)
    try:
        import _posixsubprocess

        with pytest.raises(PolicyViolation, match="subprocess"):
            # Doesn't matter what args — call should be intercepted.
            _posixsubprocess.fork_exec(
                [b"/bin/true"],
                [b"/bin/true"],
                True,
                (),
                None,
                None,
                -1,
                -1,
                -1,
                -1,
                -1,
                -1,
                -1,
                -1,
                False,
                False,
                None,
                None,
                None,
                -1,
                None,
                False,
            )
    finally:
        uninstall()


def test_subprocess_check_call_blocked():
    install(trace=False)
    try:
        import subprocess

        with pytest.raises(PolicyViolation, match="subprocess"):
            subprocess.check_call(["whatever"])
    finally:
        uninstall()


def test_nt_system_blocked():
    # On Windows, `os.system` IS `nt.system` (same function object exposed
    # under two module names). Patching `os.system` replaces the attribute on
    # the `os` module but leaves `nt.system` untouched — so any caller that
    # reaches the C-level alias (notably pickle's `find_class("nt","system")`)
    # bypasses the guard. POSIX has the same shape with `posix.*` and we patch
    # that already; `nt.*` needs the same treatment for parity.
    if sys.platform != "win32":
        pytest.skip("nt module only present on Windows")
    install(trace=False)
    try:
        import nt  # type: ignore[import-not-found]

        with pytest.raises(PolicyViolation, match="subprocess"):
            nt.system("echo should-not-run")
    finally:
        uninstall()


def test_pickle_subprocess_payload_blocked():
    # Realistic pickle attack: an attacker pickles a payload on their machine
    # (no hermetic involved), the victim's hermetic-protected process loads it.
    # Pickle's STACK_GLOBAL opcode does `find_class(module, name)`, which on
    # Windows resolves "nt"/"system" — bypassing the os.system patch unless
    # we patch nt.* too. This test pins the fix so the gap can't reopen.
    import os
    import pickle

    class Exploit:
        def __reduce__(self):
            return (os.system, ("echo should-not-run",))

    payload = pickle.dumps(Exploit())

    install(trace=False)
    try:
        with pytest.raises(PolicyViolation, match="subprocess"):
            pickle.loads(payload)
    finally:
        uninstall()
