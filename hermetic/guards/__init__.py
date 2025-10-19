from __future__ import annotations
from . import network, subprocess_guard, filesystem, imports_guard

def install_all(*, net=None, subproc=None, fs=None, imports=None):
    if net:
        network.install(**net)
    if subproc:
        subprocess_guard.install(**subproc)
    if fs:
        filesystem.install(**fs)
    if imports:
        imports_guard.install(**imports)

def uninstall_all():
    # Best-effort teardown in reverse order.
    try:
        imports_guard.uninstall()
    except Exception:
        pass
    try:
        filesystem.uninstall()
    except Exception:
        pass
    try:
        subprocess_guard.uninstall()
    except Exception:
        pass
    try:
        network.uninstall()
    except Exception:
        pass
