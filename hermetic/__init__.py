# hermetic/__init__.py
from __future__ import annotations

__all__ = ["__version__", "hermetic_blocker", "with_hermetic"]
__version__ = "0.1.0"

from .blocker import hermetic_blocker, with_hermetic  # re-export
