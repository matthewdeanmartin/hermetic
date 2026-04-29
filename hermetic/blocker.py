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
_ACTIVE_CONFIGS: list["BlockConfig"] = []
# Sealed latch: once set, _reapply_guards_locked() refuses to weaken the
# active policy and refuses to uninstall. The latch is per-process and
# never resets — opting in is an irreversible choice. Bypass requires
# walking the module's attributes via gc/inspect, which raises the bar
# above one-line removal.
_SEALED = False


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
    sealed: bool = False

    @classmethod
    def from_kwargs(cls, **kw: Any) -> "BlockConfig":
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
            "sealed": "sealed",
        }
        data: dict[str, Any] = {}
        for k, v in kw.items():
            if k not in mapping:
                raise TypeError(f"Unknown argument: {k}")
            data[mapping[k]] = v
        return cls(**data)

    def merged_with(self, other: "BlockConfig") -> "BlockConfig":
        return BlockConfig(
            block_network=self.block_network or other.block_network,
            block_subprocess=self.block_subprocess or other.block_subprocess,
            fs_readonly=self.fs_readonly or other.fs_readonly,
            fs_root=other.fs_root or self.fs_root,
            block_native=self.block_native or other.block_native,
            allow_localhost=self.allow_localhost or other.allow_localhost,
            allow_domains=list(dict.fromkeys(self.allow_domains + other.allow_domains)),
            trace=self.trace or other.trace,
            sealed=self.sealed or other.sealed,
        )


def _effective_config() -> BlockConfig:
    cfg = BlockConfig()
    for item in _ACTIVE_CONFIGS:
        cfg = cfg.merged_with(item)
    return cfg


def _install_for_config(cfg: BlockConfig) -> None:
    install_all(
        net=(
            {
                "allow_localhost": cfg.allow_localhost,
                "allow_domains": cfg.allow_domains,
                "trace": cfg.trace,
            }
            if cfg.block_network
            else None
        ),
        subproc=({"trace": cfg.trace} if cfg.block_subprocess else None),
        fs=({"fs_root": cfg.fs_root, "trace": cfg.trace} if cfg.fs_readonly else None),
        imports=(
            {
                "trace": cfg.trace,
                "block_subprocess_libs": cfg.block_subprocess,
            }
            if cfg.block_native
            else None
        ),
    )


def _reapply_guards_locked() -> None:
    if _SEALED:
        # In sealed mode, never uninstall; only widen / re-apply policy.
        if _ACTIVE_CONFIGS:
            _install_for_config(_effective_config())
        return
    uninstall_all()
    if _ACTIVE_CONFIGS:
        _install_for_config(_effective_config())


class _HermeticBlocker(
    ContextDecorator, AbstractAsyncContextManager["_HermeticBlocker"]
):
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
        global _REFCOUNT, _SEALED
        with _LOCK:
            _ACTIVE_CONFIGS.append(self.cfg)
            if self.cfg.sealed:
                _SEALED = True
            _reapply_guards_locked()
            _REFCOUNT += 1
            self._entered = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        global _REFCOUNT
        with _LOCK:
            if self._entered:
                _REFCOUNT -= 1
                self._entered = False
                try:
                    _ACTIVE_CONFIGS.remove(self.cfg)
                except ValueError:
                    pass
                _reapply_guards_locked()
        # don’t suppress exceptions

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
    sealed: bool = False,
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
        sealed=sealed,
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
