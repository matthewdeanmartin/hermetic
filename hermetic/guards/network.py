# hermetic/guards/network.py
from __future__ import annotations

import errno
import socket
import ssl
from textwrap import dedent
from typing import Any, Iterable, Never, Set

from ..errors import PolicyViolation

# State
_originals: dict[str, Any] = {}
_installed = False

# Deny well-known cloud metadata endpoints even if DNS allowed
_METADATA_HOSTS: Set[str] = {
    "169.254.169.254",  # AWS/Azure metadata
    "metadata.google.internal",  # GCP
}

_LOCALHOST = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}  # nosec


def install(
    *, allow_localhost: bool, allow_domains: Iterable[str], trace: bool = False
) -> None:
    """
    Install a network guard that preserves socket.socket as a TYPE.
    """
    global _installed
    if _installed:
        return
    _installed = True

    allowed = {d.lower().strip() for d in allow_domains if d}

    # Save originals
    _originals["socket_cls"] = socket.socket
    _originals["create_connection"] = socket.create_connection
    _originals["getaddrinfo"] = socket.getaddrinfo
    _originals["wrap_socket"] = ssl.SSLContext.wrap_socket

    def _trace(msg: str) -> None:
        if trace:
            print(f"[hermetic] {msg}", flush=True)

    def _host_from(addr: Any) -> str:
        try:
            if isinstance(addr, (tuple, list)) and len(addr) >= 1:
                return str(addr[0])
            return str(addr)
        except Exception:
            return ""

    def _is_allowed(host: str) -> bool:
        h = (host or "").lower()
        if h in _METADATA_HOSTS:
            return False
        if allow_localhost and h in _LOCALHOST:
            return True
        return any((d in h) for d in allowed)

    class GuardedSocket(_originals["socket_cls"]):  # type: ignore[valid-type, misc]
        def connect(self, address):  # type: ignore[override]
            host = _host_from(address)
            if _is_allowed(host):
                return super().connect(address)
            _trace(f"blocked socket.connect host={host} reason=no-network")
            raise PolicyViolation(f"network disabled: connect({host})")

        def connect_ex(self, address: Any) -> int:
            host = _host_from(address)
            if _is_allowed(host):
                return super().connect_ex(address)
            _trace(f"blocked socket.connect_ex host={host} reason=no-network")
            return errno.EACCES

    def create_connection_guard(address: Any, *a: Any, **k: Any) -> Never:
        host = _host_from(address)
        if _is_allowed(host):
            return _originals["create_connection"](address, *a, **k)
        _trace(f"blocked socket.create_connection host={host} reason=no-network")
        raise PolicyViolation(f"network disabled: create_connection({host})")

    def getaddrinfo_guard(host, *a, **k):
        if _is_allowed(str(host)):
            return _originals["getaddrinfo"](host, *a, **k)
        _trace(f"blocked socket.getaddrinfo host={host} reason=no-network")
        raise PolicyViolation(f"network disabled: DNS({host})")

    def wrap_socket_guard(self, sock, *a, **k):
        _trace("blocked ssl.SSLContext.wrap_socket reason=no-network")
        raise PolicyViolation("network disabled: TLS")

    socket.socket = GuardedSocket  # type: ignore[misc]
    socket.create_connection = create_connection_guard
    socket.getaddrinfo = getaddrinfo_guard
    ssl.SSLContext.wrap_socket = wrap_socket_guard


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    socket.socket = _originals["socket_cls"]  # type: ignore[misc]
    socket.create_connection = _originals["create_connection"]
    socket.getaddrinfo = _originals["getaddrinfo"]
    ssl.SSLContext.wrap_socket = _originals["wrap_socket"]
    _installed = False


# --- Code for bootstrap.py generation ---
BOOTSTRAP_CODE = dedent(
    r"""
# --- network ---
if cfg.get("no_network"):
    _orig_socket = socket.socket
    _orig_create_connection = socket.create_connection
    _orig_getaddrinfo = socket.getaddrinfo
    _orig_wrap_socket = ssl.SSLContext.wrap_socket

    ALLOW_LOCAL = bool(cfg.get("allow_localhost"))
    ALLOW_DOMAINS = set([d.lower() for d in cfg.get("allow_domains", []) if d])
    META = {"169.254.169.254", "metadata.google.internal"}
    LOCAL = {"127.0.0.1","::1","localhost","0.0.0.0"} # nosec

    def _host_from(addr):
        try:
            if isinstance(addr, (tuple, list)) and len(addr) >= 1: return str(addr[0])
            return str(addr)
        except Exception: return ""

    def _is_net_allowed(host:str)->bool:
        h = (host or "").lower()
        if h in META: return False
        if ALLOW_LOCAL and h in LOCAL: return True
        return any((d in h) for d in ALLOW_DOMAINS)

    class GuardedSocket(_orig_socket):
        def connect(self, address):
            host = _host_from(address)
            if _is_net_allowed(host): return super().connect(address)
            _tr(f"blocked socket.connect host={host}"); raise _HPolicy("network disabled")
        def connect_ex(self, address):
            host = _host_from(address)
            if _is_net_allowed(host): return super().connect_ex(address)
            _tr(f"blocked socket.connect_ex host={host}"); return errno.EACCES

    def _guard_create_connection(addr, *a, **k):
        host = _host_from(addr)
        if _is_net_allowed(host): return _orig_create_connection(addr, *a, **k)
        _tr(f"blocked socket.create_connection host={host}"); raise _HPolicy("network disabled")

    def _guard_getaddrinfo(host, *a, **k):
        if _is_net_allowed(str(host)): return _orig_getaddrinfo(host, *a, **k)
        _tr(f"blocked socket.getaddrinfo host={host}"); raise _HPolicy("network disabled")

    def _guard_wrap_socket(self, sock, *a, **k):
        _tr("blocked ssl.wrap_socket"); raise _HPolicy("network disabled")

    socket.socket = GuardedSocket
    socket.create_connection = _guard_create_connection
    socket.getaddrinfo = _guard_getaddrinfo
    ssl.SSLContext.wrap_socket = _guard_wrap_socket
"""
)
