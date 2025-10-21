# hermetic/runner.py
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

from .bootstrap import write_sitecustomize
from .errors import PolicyViolation
from .guards import install_all, uninstall_all
from .profiles import GuardConfig
from .resolver import TargetSpec, invoke_inprocess, resolve


def config_to_flags(cfg: GuardConfig) -> Dict[str, Any]:
    return {
        "no_network": cfg.no_network,
        "no_subprocess": cfg.no_subprocess,
        "fs_readonly": cfg.fs_readonly,
        "fs_root": cfg.fs_root,
        "block_native": cfg.block_native,
        "allow_localhost": cfg.allow_localhost,
        "allow_domains": cfg.allow_domains,
        "trace": cfg.trace,
    }


def run(target: str, target_argv: List[str], cfg: GuardConfig) -> int:
    spec: TargetSpec = resolve(target)

    if spec.mode == "bootstrap" and spec.exe_path and spec.interp_path:
        # sitecustomize bootstrap into foreign interpreter
        site_dir = write_sitecustomize(config_to_flags(cfg))
        env = os.environ.copy()
        # Prepend sitecustomize dir to PYTHONPATH
        env["PYTHONPATH"] = site_dir + os.pathsep + env.get("PYTHONPATH", "")
        # IMPORTANT: argv[0] should be the executable path, not the bare target string.
        # Exec the same console script path with original argv.
        # Replace current process for consistent exit code handling.
        if sys.platform == "win32":
            # On Windows, os.execve is not a true process replacement.
            # Use subprocess.run to spawn the child, wait for it, and exit
            # with its return code. This is more idiomatic for Windows.
            import subprocess  # nosec

            try:
                result = subprocess.run(  # nosec
                    [spec.exe_path] + target_argv[1:],
                    env=env,
                    check=False,
                )
                # Terminate immediately, propagating the target's exit code.
                sys.exit(result.returncode)
            except FileNotFoundError:
                print(f"hermetic: command not found: {spec.exe_path}", file=sys.stderr)
                return 127  # Standard exit code for "command not found"
        else:
            # On Unix-like systems, replace the current process for a seamless handoff.
            # This is the original, desired behavior for Linux/macOS.
            os.execve(
                spec.exe_path, [spec.exe_path] + target_argv[1:], env
            )  # never returns  # nosec

    # in-process: install guards then import/invoke
    try:
        # set argv for target exactly as provided after `--`
        sys.argv = target_argv
        install_all(
            net=(
                dict(
                    allow_localhost=cfg.allow_localhost,
                    allow_domains=cfg.allow_domains,
                    trace=cfg.trace,
                )
                if cfg.no_network
                else None
            ),
            subproc=(dict(trace=cfg.trace) if cfg.no_subprocess else None),
            fs=(
                dict(fs_root=cfg.fs_root, trace=cfg.trace) if cfg.fs_readonly else None
            ),
            imports=(dict(trace=cfg.trace) if cfg.block_native else None),
        )
        result = invoke_inprocess(spec)
        return int(result) if isinstance(result, int) else 0
    except PolicyViolation as e:
        print(f"hermetic: blocked action: {e}", file=sys.stderr)
        return 2
    finally:
        uninstall_all()
