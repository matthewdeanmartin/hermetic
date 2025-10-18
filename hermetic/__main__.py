"""
envelope - run a Python console command with networking disabled.

Usage:
  envelope <command> [--allow-localhost] [--allow-domain DOMAIN] [-- ...args...]

Examples:
  python envelope.py http https://example.com
  python envelope.py mypkg.cli:main arg1 arg2
"""

from __future__ import annotations
import sys
import argparse
import importlib
import importlib.metadata
import runpy
import socket
import types
from typing import Iterable, Sequence, Set


class NetworkBlockedError(RuntimeError):
    pass


def make_guard(allow_localhost: bool, allowed_domains: Iterable[str]):
    allowed_domains = set(d.lower().strip() for d in allowed_domains if d)
    localhost_names = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}

    def is_allowed_addr_info(addr):
        # addr is (family, type, proto, canonname, sockaddr)
        try:
            sockaddr = addr[4]
            host = sockaddr[0]
        except Exception:
            return False
        if allow_localhost and (host in localhost_names):
            return True
        # quick domain check by string containment for PoC
        for d in allowed_domains:
            if d and d in host.lower():
                return True
        return False

    def socket_factory(*args, **kwargs):
        raise NetworkBlockedError("Network access disabled by envelope (socket).")

    def create_connection_guard(address, *args, **kwargs):
        host = address[0] if isinstance(address, (tuple, list)) else address
        if allow_localhost and (host in localhost_names):
            # allow
            return original_create_connection(address, *args, **kwargs)
        for d in allowed_domains:
            if d and d in str(host).lower():
                return original_create_connection(address, *args, **kwargs)
        raise NetworkBlockedError(f"Network access disabled by envelope (create_connection to {host}).")

    def getaddrinfo_guard(host, *args, **kwargs):
        if allow_localhost and (host in localhost_names):
            return original_getaddrinfo(host, *args, **kwargs)
        for d in allowed_domains:
            if d and d in str(host).lower():
                return original_getaddrinfo(host, *args, **kwargs)
        raise NetworkBlockedError(f"Network access disabled by envelope (getaddrinfo for {host}).")

    return socket_factory, create_connection_guard, getaddrinfo_guard


def install_guard(allow_localhost: bool = False, allowed_domains: Iterable[str] = ()):
    """
    Patch socket-level APIs. Keep originals on module-level for fallback.
    """
    global original_socket, original_create_connection, original_getaddrinfo
    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    socket_factory, create_conn, getaddr = make_guard(allow_localhost, allowed_domains)

    # Replace constructors and helpers
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(NetworkBlockedError("socket() disabled by envelope"))
    socket.create_connection = create_conn
    socket.getaddrinfo = getaddr


def uninstall_guard():
    # restore originals if present (best-effort)
    try:
        socket.socket = original_socket
        socket.create_connection = original_create_connection
        socket.getaddrinfo = original_getaddrinfo
    except NameError:
        pass


def find_console_entrypoint(script_name: str):
    """
    Return tuple (module_name, attr) for console script entry points,
    or None if not found.
    """
    # importlib.metadata.entry_points() returns different shapes based on Python version.
    eps = importlib.metadata.entry_points()
    # Some Python versions: eps.select(group='console_scripts')
    try:
        console_eps = eps.select(group="console_scripts")
    except Exception:
        console_eps = [e for e in eps if getattr(e, "group", None) == "console_scripts"]

    for ep in console_eps:
        if ep.name == script_name:
            # ep.value is "module:attr"
            if ":" in ep.value:
                module, attr = ep.value.split(":", 1)
            else:
                module, attr = ep.value, "__main__"
            return module, attr
    return None


def invoke_entry(module_name: str, attr: str, argv: Sequence[str]):
    """
    Import module and call attr (callable) or run module as __main__.
    """
    # set argv for the target as it expects
    sys.argv = list(argv)

    # if attr is "__main__", run the module as script
    if attr in ("__main__", "main"):
        # We try to import and call main if exists, else run module as __main__
        mod = importlib.import_module(module_name)
        if hasattr(mod, "main") and callable(getattr(mod, "main")) and attr == "main":
            return mod.main()
        # fallback: run module as script
        return runpy.run_module(module_name, run_name="__main__")
    else:
        mod = importlib.import_module(module_name)
        func = getattr(mod, attr)
        if callable(func):
            return func()
        raise RuntimeError(f"Entry point attribute {attr} in {module_name} is not callable.")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="envelope", description="Run a Python console script with networking disabled.")
    p.add_argument("--allow-localhost", action="store_true", help="Allow localhost connections.")
    p.add_argument("--allow-domain", action="append", default=[], help="Allow connections to domain substring (can repeat).")
    p.add_argument("target", help="Target command (console script name, or module[:callable]).")
    p.add_argument("target_args", nargs=argparse.REMAINDER, help="Arguments passed to target. Prefix -- to separate.")
    return p.parse_args(argv)


def resolve_target(spec: str):
    """
    Accept formats:
      - name (console script)
      - module:callable
      - module (fallback to running module as __main__)
    Returns (module, attr_or_main)
    """
    if ":" in spec:
        m, a = spec.split(":", 1)
        return m, a
    # try console script resolution
    ep = find_console_entrypoint(spec)
    if ep:
        return ep
    # fallback: treat spec as module name to run as __main__
    return spec, "__main__"


def main(argv: Sequence[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ns = parse_args(argv)

    # target and its args
    target_spec = ns.target
    target_argv = ns.target_args or []
    if target_argv and target_argv[0] == "--":
        target_argv = target_argv[1:]

    module_name, attr = resolve_target(target_spec)

    install_guard(allow_localhost=ns.allow_localhost, allowed_domains=ns.allow_domain)

    try:
        try:
            result = invoke_entry(module_name, attr, [target_spec] + target_argv)
            # If the target returns an int, treat as exit code
            if isinstance(result, int):
                return result
            return 0
        except NetworkBlockedError as e:
            print(f"envelope: blocked network call: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            # If the target raised something else, re-raise after tearing down guard so tracebacks are not masked
            raise
    finally:
        uninstall_guard()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # let full traceback print
        raise
