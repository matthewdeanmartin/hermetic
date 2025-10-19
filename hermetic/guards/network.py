# hermetic/guards/network.py
from __future__ import annotations
import errno
import socket
import ssl
from typing import Iterable, Set, Tuple, Any
from ..errors import PolicyViolation

# State
_originals: dict[str, Any] = {}
_installed = False

# Deny well-known cloud metadata endpoints even if DNS allowed
_METADATA_HOSTS: Set[str] = {
    "169.254.169.254",        # AWS/Azure metadata
    "metadata.google.internal"  # GCP
}

_LOCALHOST = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


def install(*, allow_localhost: bool, allow_domains: Iterable[str], trace: bool = False):
    """
    Install a network guard that preserves socket.socket as a TYPE.

    Strategy:
      - Replace socket.socket with a subclass that blocks connect/connect_ex.
      - Guard socket.create_connection, socket.getaddrinfo.
      - Guard ssl.SSLContext.wrap_socket (fast fail on TLS).
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

    def _trace(msg: str):
        if trace:
            # stderr not strictly required; stdout is acceptable for PoC
            print(f"[hermetic] {msg}", flush=True)

    def _host_from(addr: Any) -> str:
        # create_connection and connect accept different shapes
        # Common case: (host, port)
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

    # Subclass the real socket class so third-party "class X(socket.socket)" still works.
    class GuardedSocket(_originals["socket_cls"]):  # type: ignore[misc]
        def connect(self, address):  # type: ignore[override]
            host = _host_from(address)
            if _is_allowed(host):
                return super().connect(address)
            _trace(f"blocked socket.connect host={host} reason=no-network")
            raise PolicyViolation(f"network disabled: connect({host})")

        def connect_ex(self, address):  # type: ignore[override]
            host = _host_from(address)
            if _is_allowed(host):
                return super().connect_ex(address)
            _trace(f"blocked socket.connect_ex host={host} reason=no-network")
            # connect_ex convention is errno int; we surface policy while remaining compatible.
            # Many callers treat nonzero as failure. EACCES/EPERM are reasonable.
            return errno.EACCES

    def create_connection_guard(address, *a, **k):
        host = _host_from(address)
        if _is_allowed(host):
            return _originals["create_connection"](address, *a, **k)  # type: ignore[misc]
        _trace(f"blocked socket.create_connection host={host} reason=no-network")
        raise PolicyViolation(f"network disabled: create_connection({host})")

    def getaddrinfo_guard(host, *a, **k):
        if _is_allowed(str(host)):
            return _originals["getaddrinfo"](host, *a, **k)  # type: ignore[misc]
        _trace(f"blocked socket.getaddrinfo host={host} reason=no-network")
        raise PolicyViolation(f"network disabled: DNS({host})")

    def wrap_socket_guard(self, sock, *a, **k):  # bound method
        _trace("blocked ssl.SSLContext.wrap_socket reason=no-network")
        raise PolicyViolation("network disabled: TLS")

    # Install
    socket.socket = GuardedSocket  # type: ignore[assignment]
    socket.create_connection = create_connection_guard  # type: ignore[assignment]
    socket.getaddrinfo = getaddrinfo_guard  # type: ignore[assignment]
    ssl.SSLContext.wrap_socket = wrap_socket_guard  # type: ignore[assignment]


def uninstall():
    global _installed
    if not _installed:
        return
    # Restore originals
    socket.socket = _originals["socket_cls"]  # type: ignore[assignment]
    socket.create_connection = _originals["create_connection"]  # type: ignore[assignment]
    socket.getaddrinfo = _originals["getaddrinfo"]  # type: ignore[assignment]
    ssl.SSLContext.wrap_socket = _originals["wrap_socket"]  # type: ignore[assignment]
    _installed = False
