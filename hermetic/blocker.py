# hermetic/blocker.py
from __future__ import annotations

import threading
from contextlib import AbstractAsyncContextManager, ContextDecorator
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional

from .guards import install_all, uninstall_all

# Process-wide, reentrant reference count for guard activation.
# Guards are global monkey-patches; we only uninstall when the outermost scope exits.
_LOCK = threading.RLock()
_REFCOUNT = 0


@dataclass
class BlockConfig:
    block_network: bool = False
    block_subprocess: bool = False
    fs_readonly: bool = False
    fs_root: Optional[str] = None
    block_native: bool = False
    allow_localhost: bool = False
    allow_domains: List[str] = field(default_factory=list)
    trace: bool = False

    @classmethod
    def from_kwargs(cls, **kw) -> "BlockConfig":
        # Accept both long and short kw names
        mapping = {
            "block_network": "block_network",
            "no_network": "block_network",
            "block_subprocess": "block_subprocess",
            "no_subprocess": "block_subprocess",
            "fs_readonly": "fs_readonly",
            "fs_root": "fs_root",
            "block_native": "block_native",
            "allow_localhost": "allow_localhost",
            "allow_domains": "allow_domains",
            "trace": "trace",
        }
        data = {}
        for k, v in kw.items():
            if k not in mapping:
                raise TypeError(f"Unknown argument: {k}")
            data[mapping[k]] = v
        return cls(**data)


class _HermeticBlocker(ContextDecorator, AbstractAsyncContextManager):
    """
    Context manager / decorator to install hermetic guards for the current process.

    Notes:
      - Global monkey-patches affect all threads in this interpreter.
      - Safe to nest; guards are installed once and reference-counted.
      - Async-compatible: `async with hermetic_blocker(...): ...`
    """

    __slots__ = ("cfg", "_entered")

    def __init__(self, cfg: BlockConfig) -> None:
        self.cfg = cfg
        self._entered = False

    # ---- sync protocol ----
    def __enter__(self) -> "_HermeticBlocker":
        global _REFCOUNT
        with _LOCK:
            if _REFCOUNT == 0:
                install_all(
                    net=(
                        dict(
                            allow_localhost=self.cfg.allow_localhost,
                            allow_domains=self.cfg.allow_domains,
                            trace=self.cfg.trace,
                        )
                        if self.cfg.block_network
                        else None
                    ),
                    subproc=(
                        dict(trace=self.cfg.trace)
                        if self.cfg.block_subprocess
                        else None
                    ),
                    fs=(
                        dict(fs_root=self.cfg.fs_root, trace=self.cfg.trace)
                        if self.cfg.fs_readonly
                        else None
                    ),
                    imports=(
                        dict(trace=self.cfg.trace) if self.cfg.block_native else None
                    ),
                )
            _REFCOUNT += 1
            self._entered = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        global _REFCOUNT
        with _LOCK:
            if self._entered:
                _REFCOUNT -= 1
                self._entered = False
                if _REFCOUNT == 0:
                    uninstall_all()
        # don’t suppress exceptions
        return None

    # ---- async protocol ----
    async def __aenter__(self) -> "_HermeticBlocker":
        # Reuse sync enter; safe in async contexts
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return self.__exit__(exc_type, exc, tb)


def hermetic_blocker(
    *,
    block_network: bool = False,
    block_subprocess: bool = False,
    fs_readonly: bool = False,
    fs_root: Optional[str] = None,
    block_native: bool = False,
    allow_localhost: bool = False,
    allow_domains: Iterable[str] = (),
    trace: bool = False,
) -> _HermeticBlocker:
    """
    Public constructor. Usage:

        with hermetic_blocker(block_network=True, block_subprocess=True):
            ...

    Also valid as a decorator:

        @hermetic_blocker(block_network=True)
        def run():
            ...
    """
    cfg = BlockConfig(
        block_network=block_network,
        block_subprocess=block_subprocess,
        fs_readonly=fs_readonly,
        fs_root=fs_root,
        block_native=block_native,
        allow_localhost=allow_localhost,
        allow_domains=list(allow_domains or ()),
        trace=trace,
    )
    return _HermeticBlocker(cfg)


# Optional convenience decorator with arguments name parity
def with_hermetic(**kwargs: Any) -> _HermeticBlocker:
    """
    Decorator factory mirroring hermetic_blocker kwargs.

        @with_hermetic(block_network=True, allow_localhost=True)
        def main(): ...
    """
    return hermetic_blocker(**kwargs)
