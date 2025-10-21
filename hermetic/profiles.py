# hermetic/profiles.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class GuardConfig:
    no_network: bool = False
    no_subprocess: bool = False
    fs_readonly: bool = False
    fs_root: str | None = None
    block_native: bool = False
    allow_localhost: bool = False
    allow_domains: List[str] = field(default_factory=list)
    trace: bool = False


PROFILES: dict[str, GuardConfig] = {
    "block-all": GuardConfig(block_native=True,no_subprocess=True,no_network=True,fs_readonly=True),
    "net-hermetic": GuardConfig(no_network=True, allow_localhost=True),
    "exec-deny": GuardConfig(no_subprocess=True),
    "fs-readonly": GuardConfig(fs_readonly=True),
    "block-native": GuardConfig(block_native=True),
}


def apply_profile(base: GuardConfig, name: str) -> GuardConfig:
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
