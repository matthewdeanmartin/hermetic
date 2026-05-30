"""Context managers and decorators for process-wide guard activation."""

from __future__ import annotations

import threading
from contextlib import AbstractAsyncContextManager, ContextDecorator
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional

from hermetic.guards import install_all, uninstall_all

# Process-wide merged policy state for guard activation.
_LOCK = threading.RLock()
_ACTIVE_CONFIGS: list["BlockConfig"] = []
# Sealed latch: once set, _reapply_guards_locked() refuses to weaken the
# active policy and refuses to uninstall. The latch is per-process and
# never resets — opting in is an irreversible choice. Bypass requires
# walking the module's attributes via gc/inspect, which raises the bar
# above one-line removal.
_SEALED = False


@dataclass
class BlockConfig:
    """Describe the guard policy contributed by one blocker instance."""

    block_network: bool = False
    block_subprocess: bool = False
    fs_readonly: bool = False
    fs_root: Optional[str] = None
    block_environment: bool = False
    block_code_exec: bool = False
    block_interpreter_mutation: bool = False
    block_native: bool = False
    allow_localhost: bool = False
    allow_domains: List[str] = field(default_factory=list)
    deny_imports: List[str] = field(default_factory=list)
    trace: bool = False
    sealed: bool = False

    @classmethod
    def from_kwargs(cls, **kw: Any) -> "BlockConfig":
        """Normalize accepted keyword aliases into a config instance."""
        # Accept both long and short kw names
        mapping = {
            "block_network": "block_network",
            "no_network": "block_network",
            "block_subprocess": "block_subprocess",
            "no_subprocess": "block_subprocess",
            "fs_readonly": "fs_readonly",
            "fs_root": "fs_root",
            "block_environment": "block_environment",
            "no_environment": "block_environment",
            "no_env": "block_environment",
            "block_code_exec": "block_code_exec",
            "no_code_exec": "block_code_exec",
            "block_interpreter_mutation": "block_interpreter_mutation",
            "no_interpreter_mutation": "block_interpreter_mutation",
            "block_native": "block_native",
            "allow_localhost": "allow_localhost",
            "allow_domains": "allow_domains",
            "deny_imports": "deny_imports",
            "trace": "trace",
            "sealed": "sealed",
        }
        data: dict[str, Any] = {}
        for k, v in kw.items():
            if k not in mapping:
                raise TypeError(f"Unknown argument: {k}")
            data[mapping[k]] = v
        return cls(**data)

    def __or__(self, other: "BlockConfig") -> "BlockConfig":
        """Merge two policies; stricter settings win.  Alias for ``merged_with``."""
        return self.merged_with(other)

    def merged_with(self, other: "BlockConfig") -> "BlockConfig":
        """Combine two policies so the stricter settings win."""
        return BlockConfig(
            block_network=self.block_network or other.block_network,
            block_subprocess=self.block_subprocess or other.block_subprocess,
            fs_readonly=self.fs_readonly or other.fs_readonly,
            fs_root=other.fs_root or self.fs_root,
            block_environment=self.block_environment or other.block_environment,
            block_code_exec=self.block_code_exec or other.block_code_exec,
            block_interpreter_mutation=(
                self.block_interpreter_mutation or other.block_interpreter_mutation
            ),
            block_native=self.block_native or other.block_native,
            allow_localhost=self.allow_localhost or other.allow_localhost,
            allow_domains=list(dict.fromkeys(self.allow_domains + other.allow_domains)),
            deny_imports=list(dict.fromkeys(self.deny_imports + other.deny_imports)),
            trace=self.trace or other.trace,
            sealed=self.sealed or other.sealed,
        )


def _effective_config() -> BlockConfig:
    """Merge all active blocker configs into one effective policy."""
    cfg = BlockConfig()
    for item in _ACTIVE_CONFIGS:
        cfg = cfg.merged_with(item)
    return cfg


def _install_for_config(cfg: BlockConfig) -> None:
    """Install the guard set described by a merged blocker config."""
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
        env=({"trace": cfg.trace} if cfg.block_environment else None),
        code=({"trace": cfg.trace} if cfg.block_code_exec else None),
        interp=({"trace": cfg.trace} if cfg.block_interpreter_mutation else None),
        imports=(
            {
                "block_native": cfg.block_native,
                "trace": cfg.trace,
                "block_subprocess_libs": cfg.block_subprocess,
                "block_pickle": cfg.block_code_exec,
                "deny_imports": cfg.deny_imports,
            }
            if cfg.block_native or cfg.deny_imports or cfg.block_code_exec
            else None
        ),
    )


def _reapply_guards_locked() -> None:
    """Reinstall guards to reflect the current active blocker stack."""
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
    """Manage a blocker policy as a sync or async context manager."""

    __slots__ = ("cfg", "_entered")

    def __init__(self, cfg: BlockConfig) -> None:
        """Store the policy that should be applied on entry."""
        self.cfg = cfg
        self._entered = False

    # ---- sync protocol ----
    def __enter__(self) -> "_HermeticBlocker":
        """Activate this blocker policy for the current process."""
        global _SEALED
        with _LOCK:
            _ACTIVE_CONFIGS.append(self.cfg)
            if self.cfg.sealed:
                _SEALED = True
            _reapply_guards_locked()
            self._entered = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Remove this blocker policy and restore the merged state."""
        with _LOCK:
            if self._entered:
                self._entered = False
                try:
                    _ACTIVE_CONFIGS.remove(self.cfg)
                except ValueError:
                    pass
                _reapply_guards_locked()
        # don’t suppress exceptions

    # ---- async protocol ----
    async def __aenter__(self) -> "_HermeticBlocker":
        """Activate the blocker policy inside an async context."""
        # Reuse sync enter; safe in async contexts
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Tear down the blocker policy after an async context exits."""
        return self.__exit__(exc_type, exc, tb)


def hermetic_blocker(
    _config: Optional[BlockConfig] = None,
    *,
    block_network: bool = False,
    block_subprocess: bool = False,
    fs_readonly: bool = False,
    fs_root: Optional[str] = None,
    block_environment: bool = False,
    block_code_exec: bool = False,
    block_interpreter_mutation: bool = False,
    block_native: bool = False,
    allow_localhost: bool = False,
    allow_domains: Iterable[str] = (),
    deny_imports: Iterable[str] = (),
    trace: bool = False,
    sealed: bool = False,
    profile: Optional[str] = None,
) -> _HermeticBlocker:
    """Build a blocker that applies the requested hermetic guards.

    Can be called in three ways::

        # 1. Keyword arguments (original API)
        hermetic_blocker(block_network=True)

        # 2. Pre-built BlockConfig object
        hermetic_blocker(BlockConfig(block_network=True))

        # 3. Named profile
        hermetic_blocker(profile="net-hermetic")
    """
    if _config is not None:
        if not isinstance(_config, BlockConfig):
            raise TypeError(
                f"hermetic_blocker() positional argument must be a BlockConfig, got {type(_config).__name__}"
            )
        cfg = _config
    else:
        cfg = BlockConfig(
            block_network=block_network,
            block_subprocess=block_subprocess,
            fs_readonly=fs_readonly,
            fs_root=fs_root,
            block_environment=block_environment,
            block_code_exec=block_code_exec,
            block_interpreter_mutation=block_interpreter_mutation,
            block_native=block_native,
            allow_localhost=allow_localhost,
            allow_domains=list(allow_domains or ()),
            deny_imports=list(deny_imports or ()),
            trace=trace,
            sealed=sealed,
        )

    if profile is not None:
        from hermetic.profiles import PROFILES  # avoid circular at module level

        prof = PROFILES.get(profile)
        if prof is None:
            raise ValueError(f"Unknown hermetic profile: {profile!r}")
        # Convert GuardConfig → BlockConfig fields and merge
        profile_cfg = BlockConfig(
            block_network=prof.no_network,
            block_subprocess=prof.no_subprocess,
            fs_readonly=prof.fs_readonly,
            fs_root=prof.fs_root,
            block_environment=prof.no_environment,
            block_code_exec=prof.no_code_exec,
            block_interpreter_mutation=prof.no_interpreter_mutation,
            block_native=prof.block_native,
            allow_localhost=prof.allow_localhost,
            allow_domains=list(prof.allow_domains),
            deny_imports=list(prof.deny_imports),
            trace=prof.trace,
            sealed=prof.sealed,
        )
        cfg = cfg | profile_cfg

    return _HermeticBlocker(cfg)


# Optional convenience decorator with arguments name parity
def with_hermetic(
    _config: Optional[BlockConfig] = None, **kwargs: Any
) -> _HermeticBlocker:
    """Mirror `hermetic_blocker` under a decorator-friendly name."""
    return hermetic_blocker(_config, **kwargs)
