# hermetic/errors.py
from __future__ import annotations


class HermeticError(RuntimeError):
    """Base for hermetic failures."""


class PolicyViolation(HermeticError):
    """Raised when a guard blocks an action."""


class BootstrapError(HermeticError):
    """Raised when bootstrap mode fails."""
