"""Named guard presets and helpers for combining them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class GuardConfig:
    """Capture the guard settings used to run a target."""

    no_network: bool = False
    no_subprocess: bool = False
    fs_readonly: bool = False
    fs_root: str | None = None
    no_environment: bool = False
    no_code_exec: bool = False
    no_interpreter_mutation: bool = False
    block_native: bool = False
    allow_localhost: bool = False
    allow_domains: List[str] = field(default_factory=list)
    deny_imports: List[str] = field(default_factory=list)
    trace: bool = False
    sealed: bool = False


PROFILES: dict[str, GuardConfig] = {
    "block-all": GuardConfig(
        block_native=True,
        no_subprocess=True,
        no_network=True,
        fs_readonly=True,
        no_environment=True,
        no_code_exec=True,
        no_interpreter_mutation=True,
    ),
    "net-hermetic": GuardConfig(no_network=True, allow_localhost=True),
    "exec-deny": GuardConfig(no_subprocess=True),
    "fs-readonly": GuardConfig(fs_readonly=True),
    "block-native": GuardConfig(block_native=True),
}


def apply_profile(base: GuardConfig, name: str) -> GuardConfig:
    """Overlay a named profile onto an existing guard config."""
    prof = PROFILES.get(name)
    if not prof:
        raise SystemExit(f"unknown profile: {name}")
    # Merge 'truthy' fields from profile into base.
    merged = GuardConfig(**vars(base))
    for k, v in vars(prof).items():
        if isinstance(v, bool) and v:
            setattr(merged, k, True)
        elif isinstance(v, list) and v:
            getattr(merged, k).extend(v)
        elif isinstance(v, str) and v:
            setattr(merged, k, v)
    return merged
