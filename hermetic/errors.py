# hermetic/errors.py
"""Exception types raised by hermetic guard setup and enforcement."""

from __future__ import annotations


class HermeticError(RuntimeError):
    """Base for hermetic failures."""


class PolicyViolation(HermeticError):
    """Raised when a guard blocks an action.

    Attributes:
        guard: Machine-readable guard name (e.g. ``"network"``, ``"subprocess"``,
               ``"filesystem"``, ``"environment"``, ``"code_exec"``,
               ``"interpreter"``, ``"imports"``).  ``None`` when the violation
               originates from code that predates this attribute.
        target: Optional detail about what was blocked (host, path, import name…).
    """

    guard: str | None
    target: str | None

    def __init__(
        self,
        message: str,
        *,
        guard: str | None = None,
        target: str | None = None,
    ) -> None:
        """Create a policy violation with an optional machine-readable guard name."""
        super().__init__(message)
        self.guard = guard
        self.target = target


class BootstrapError(HermeticError):
    """Raised when bootstrap mode fails."""
