# hermetic/cli.py
from __future__ import annotations

import argparse
import sys
from typing import List

from . import __version__
from .profiles import GuardConfig, apply_profile
from .runner import run
from .util import split_argv

EXAMPLES = """\
examples:
  hermetic --no-network -- http https://example.com
  hermetic --no-network --allow-localhost --no-subprocess -- myapp --serve
  hermetic --fs-readonly=./sandbox --block-native -- target-cli --opt
notes:
  Use `--` to separate hermetic's flags from the target's flags to avoid collisions.
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hermetic",
        description="Run a Python console script with user-space sandbox guards.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )
    # Core flags
    p.add_argument(
        "--no-network", action="store_true", help="Disable outbound network and DNS."
    )
    p.add_argument(
        "--allow-localhost", action="store_true", help="Allow localhost network."
    )
    p.add_argument(
        "--allow-domain",
        action="append",
        default=[],
        help="Allow connections to domain substring (repeatable).",
    )
    p.add_argument(
        "--no-subprocess", action="store_true", help="Disable subprocess execution."
    )
    p.add_argument(
        "--fs-readonly",
        nargs="?",
        const="__ENABLED__",
        help="Make filesystem readonly; optional =ROOT constrains reads.",
    )
    p.add_argument(
        "--block-native",
        action="store_true",
        help="Deny native extensions and FFI modules.",
    )
    p.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Apply a named profile (repeatable).",
    )
    p.add_argument(
        "--trace", action="store_true", help="Trace blocked actions to stderr."
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--", dest="--", action="store_true", help=argparse.SUPPRESS
    )  # placeholder to show intent in help
    return p


def parse_hermetic_args(argv: List[str]) -> GuardConfig:
    parser = build_parser()
    ns = parser.parse_args(argv)
    cfg = GuardConfig(
        no_network=bool(ns.no_network),
        no_subprocess=bool(ns.no_subprocess),
        fs_readonly=bool(ns.fs_readonly),
        fs_root=(
            None if ns.fs_readonly in (None, "__ENABLED__") else str(ns.fs_readonly)
        ),
        block_native=bool(ns.block_native),
        allow_localhost=bool(ns.allow_localhost),
        allow_domains=list(ns.allow_domain or []),
        trace=bool(ns.trace),
    )
    for prof in ns.profile or []:
        cfg = apply_profile(cfg, prof)
    return cfg


def main(argv: List[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    split = split_argv(argv)

    # If user asked only for help/version (no target segment), show help and exit 0.
    if not split.target_argv:
        # parse so --version works; argparse will print help for -h/--help
        _ = parse_hermetic_args(split.hermetic_argv)
        # If we reached here without SystemExit, no version/help was triggered.
        # Print help explicitly for UX.
        build_parser().print_help()
        return 0

    cfg = parse_hermetic_args(split.hermetic_argv)
    # target argv after `--` must exist
    if not split.target_argv:
        raise SystemExit("usage error: missing target after `--`")
    target = split.target_argv[0]
    target_argv = split.target_argv
    return run(target, target_argv, cfg)
