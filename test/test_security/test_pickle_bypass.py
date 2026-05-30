"""Pickle / marshal / shelve denial under --no-code-exec.

Pickle's `find_class(module, name)` lets an attacker-controlled byte stream
name *any* importable callable and have pickle invoke it. The guards can't
realistically patch every reachable function, so when the user has signaled
"no dynamic code execution", we auto-deny imports of pickle and its
siblings. A plugin that genuinely needs serialization can use JSON,
configparser, etc.; pickle is never *required*.
"""

from __future__ import annotations

import sys

import pytest

from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation
from hermetic.guards.imports_guard import install, uninstall


def test_imports_guard_denies_pickle_when_block_pickle():
    # Direct guard-level test: the new block_pickle kwarg adds the
    # serialization modules to the deny set.
    sys.modules.pop("pickle", None)
    install(trace=False, block_native=False, block_pickle=True)
    try:
        with pytest.raises(PolicyViolation, match="import blocked: pickle"):
            import pickle  # noqa: F401
    finally:
        uninstall()


def test_imports_guard_denies_marshal_when_block_pickle():
    sys.modules.pop("marshal", None)
    install(trace=False, block_native=False, block_pickle=True)
    try:
        with pytest.raises(PolicyViolation, match="import blocked: marshal"):
            import marshal  # noqa: F401
    finally:
        uninstall()


def test_imports_guard_denies_shelve_when_block_pickle():
    sys.modules.pop("shelve", None)
    install(trace=False, block_native=False, block_pickle=True)
    try:
        with pytest.raises(PolicyViolation, match="import blocked: shelve"):
            import shelve  # noqa: F401
    finally:
        uninstall()


def test_imports_guard_allows_pickle_when_not_set():
    sys.modules.pop("pickle", None)
    install(trace=False, block_native=False, block_pickle=False)
    try:
        import pickle  # noqa: F401
    finally:
        uninstall()


def test_no_code_exec_auto_denies_pickle():
    # Composition rule: requesting block_code_exec should imply pickle is
    # denied, even if the caller didn't list it explicitly in deny_imports.
    sys.modules.pop("pickle", None)
    with hermetic_blocker(block_code_exec=True):
        with pytest.raises(PolicyViolation, match="import blocked: pickle"):
            import pickle  # noqa: F401


def test_no_code_exec_auto_denies_marshal():
    sys.modules.pop("marshal", None)
    with hermetic_blocker(block_code_exec=True):
        with pytest.raises(PolicyViolation, match="import blocked: marshal"):
            import marshal  # noqa: F401


def test_no_code_exec_blocks_pickle_loads_payload():
    # End-to-end: the realistic threat is a payload built elsewhere and
    # unpickled inside the guarded process. With --no-code-exec, the import
    # is refused before find_class ever runs.
    import os
    import pickle

    class Exploit:
        def __reduce__(self):
            return (os.system, ("echo should-not-run",))

    payload = pickle.dumps(Exploit())

    sys.modules.pop("pickle", None)
    with hermetic_blocker(block_code_exec=True, block_subprocess=True):
        with pytest.raises(PolicyViolation, match="import blocked: pickle"):
            import pickle as _pickle  # noqa: F401

            _pickle.loads(payload)


def test_pickle_allowed_without_code_exec_flag():
    # If the user hasn't enabled --no-code-exec, pickle should still load.
    # Hermetic doesn't unilaterally deny everything dangerous; it follows
    # the policy the caller asked for.
    sys.modules.pop("pickle", None)
    with hermetic_blocker(block_subprocess=True):
        import pickle  # noqa: F401
