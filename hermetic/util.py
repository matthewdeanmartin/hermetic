# hermetic/utilmake_prompt.sh
# make_source.sh.py
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SplitArgs:
    hermetic_argv: List[str]
    target_argv: List[str]


_HELP_TOKENS = {"-h", "--help", "--version"}


def split_argv(argv: list[str]) -> SplitArgs:
    """
    Split command line into hermetic vs target segments.

    Rules:
      - If '--' present, split there.
      - If no '--' and any of {-h, --help, --version} present, treat as hermetic-only.
      - Otherwise, require '--' to avoid flag collisions.
    """
    if "--" in argv:
        idx = argv.index("--")
        return SplitArgs(argv[:idx], argv[idx + 1 :])

    if any(tok in argv for tok in _HELP_TOKENS):
        return SplitArgs(argv, [])

    raise SystemExit("usage error: separate hermetic and target args with `--`")


def is_same_interpreter(exe_path: str) -> bool:
    # Compare normalized sys.executable with resolved shebang interpreter path.
    try:
        here = os.path.realpath(sys.executable)
        there = os.path.realpath(exe_path)
        return here == there
    except Exception:
        return False


def which(exe_name: str) -> str | None:
    return shutil.which(exe_name)
