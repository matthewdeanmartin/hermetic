# hermetic/guards/__init__.py
# This file makes the 'guards' directory a package.
from typing import Any

from . import subprocess_guard  # nosec
from . import filesystem, imports_guard, network

# This makes install_all and uninstall_all easily accessible.
_all_guards = (filesystem, imports_guard, network, subprocess_guard)


def install_all(**kwargs: Any) -> None:
    if kwargs.get("net"):
        network.install(**kwargs["net"])
    if kwargs.get("subproc"):
        subprocess_guard.install(**kwargs["subproc"])
    if kwargs.get("fs"):
        filesystem.install(**kwargs["fs"])
    if kwargs.get("imports"):
        imports_guard.install(**kwargs["imports"])


def uninstall_all() -> None:
    for guard in reversed(_all_guards):
        guard.uninstall()
