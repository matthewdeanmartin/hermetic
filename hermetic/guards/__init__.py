"""Guard module orchestration for bulk install and uninstall operations."""

from typing import Any

from . import imports_guard  # nosec
from . import interpreter  # nosec
from . import code_exec, environment, filesystem, network, subprocess_guard

# This makes install_all and uninstall_all easily accessible.
_all_guards = (
    code_exec,
    environment,
    filesystem,
    imports_guard,
    interpreter,
    network,
    subprocess_guard,
)


def install_all(**kwargs: Any) -> None:
    """Install every requested guard using grouped keyword options."""
    if kwargs.get("net"):
        network.install(**kwargs["net"])
    if kwargs.get("subproc"):
        subprocess_guard.install(**kwargs["subproc"])
    if kwargs.get("fs"):
        filesystem.install(**kwargs["fs"])
    if kwargs.get("env"):
        environment.install(**kwargs["env"])
    if kwargs.get("code"):
        code_exec.install(**kwargs["code"])
    if kwargs.get("imports"):
        imports_guard.install(**kwargs["imports"])
    if kwargs.get("interp"):
        interpreter.install(**kwargs["interp"])


def uninstall_all() -> None:
    """Remove installed guards in reverse dependency order."""
    for guard in reversed(_all_guards):
        guard.uninstall()
