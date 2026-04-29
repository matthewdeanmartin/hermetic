# hermetic/__init__.py
from __future__ import annotations

__all__ = ["__version__", "hermetic_blocker", "with_hermetic"]
from hermetic.__about__ import __version__

from .blocker import hermetic_blocker, with_hermetic  # re-export
