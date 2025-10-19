# hermetic/runner.py
from __future__ import annotations
import os
import sys
from typing import Any, Dict, List
from .profiles import GuardConfig, apply_profile
from .guards import install_all, uninstall_all
from .resolver import TargetSpec, resolve, invoke_inprocess
from .bootstrap import write_sitecustomize
from .errors import PolicyViolation, BootstrapError

def config_to_flags(cfg: GuardConfig) -> Dict[str, Any]:
    return {
        "no_network": cfg.no_network,
        "no_subprocess": cfg.no_subprocess,
        "fs_readonly": cfg.fs_readonly,
        "fs_root": cfg.fs_root,
        "strict_imports": cfg.strict_imports,
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
        os.execve(spec.exe_path, [spec.exe_path] + target_argv[1:], env)   # never returns

    # if spec.mode == "bootstrap" and spec.exe_path and spec.interp_path:
    #     site_dir = write_sitecustomize(config_to_flags(cfg))
    #     env = os.environ.copy()
    #     env["PYTHONPATH"] = site_dir + os.pathsep + env.get("PYTHONPATH", "")
    #     os.execve(spec.exe_path, [target] + target_argv[1:], env)  # never returns

    # in-process: install guards then import/invoke
    try:
        # set argv for target exactly as provided after `--`
        sys.argv = target_argv
        install_all(
            net=(dict(allow_localhost=cfg.allow_localhost,
                      allow_domains=cfg.allow_domains,
                      trace=cfg.trace) if cfg.no_network else None),
            subproc=(dict(trace=cfg.trace) if cfg.no_subprocess else None),
            fs=(dict(fs_root=cfg.fs_root, trace=cfg.trace) if cfg.fs_readonly else None),
            imports=(dict(trace=cfg.trace) if cfg.strict_imports else None),
        )
        result = invoke_inprocess(spec)
        return int(result) if isinstance(result, int) else 0
    except PolicyViolation as e:
        print(f"hermetic: blocked action: {e}", file=sys.stderr)
        return 2
    finally:
        uninstall_all()
