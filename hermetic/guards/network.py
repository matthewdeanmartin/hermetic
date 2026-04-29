# hermetic/guards/network.py
"""Guards that block outbound networking and unsafe bind targets."""

from __future__ import annotations

import errno
import socket
import ssl
import sys
from textwrap import dedent
from typing import Any, Iterable, Set

from hermetic.errors import PolicyViolation

# State
_originals: dict[str, Any] = {}
_installed = False

# Deny well-known cloud metadata endpoints even if DNS allowed.
# IPv6 forms and link-local SLAAC variants included — AWS IMDSv2 supports
# IPv6 at fd00:ec2::254; the IPv4 metadata IP also has an IPv6-mapped form.
_METADATA_HOSTS: Set[str] = {
    "169.254.169.254",  # AWS/Azure/OpenStack/DigitalOcean metadata
    "metadata.google.internal",  # GCP
    "metadata",  # short-form GCP alias when search-domain matches
    "fd00:ec2::254",  # AWS IMDSv2 IPv6
    "fd00:ec2:0:0:0:0:0:254",
    "fe80::a9fe:a9fe",  # link-local SLAAC variant
    "100.100.100.200",  # Alibaba Cloud metadata
}

_LOCALHOST = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}  # nosec


def _normalize_host(host: str) -> str:
    """Normalize a hostname for policy checks."""
    return (host or "").strip().lower().rstrip(".")


def _domain_matches(host: str, domain: str) -> bool:
    """Check whether a host is equal to or inside an allowed domain."""
    h = _normalize_host(host)
    d = _normalize_host(domain)
    return bool(d) and (h == d or h.endswith(f".{d}"))


def install(
    *, allow_localhost: bool, allow_domains: Iterable[str], trace: bool = False
) -> None:
    """Patch networking APIs while keeping `socket.socket` subclassable."""
    global _installed
    if _installed:
        return
    _installed = True

    allowed = {d.lower().strip() for d in allow_domains if d}

    # Save originals
    _originals["socket_cls"] = socket.socket
    _originals["SocketType"] = getattr(socket, "SocketType", None)
    _originals["create_connection"] = socket.create_connection
    _originals["getaddrinfo"] = socket.getaddrinfo
    _originals["gethostbyname"] = socket.gethostbyname
    _originals["gethostbyname_ex"] = socket.gethostbyname_ex
    _originals["wrap_socket"] = ssl.SSLContext.wrap_socket
    if hasattr(socket, "socketpair"):
        _originals["socketpair"] = socket.socketpair
    if hasattr(socket, "fromfd"):
        _originals["fromfd"] = socket.fromfd
    if hasattr(socket, "fromshare"):
        _originals["fromshare"] = socket.fromshare

    def _trace(msg: str) -> None:
        """Emit a trace message when network access is blocked."""
        if trace:
            print(f"[hermetic] {msg}", file=sys.stderr, flush=True)

    def _host_from(addr: Any) -> str:
        """Extract the host component from a socket-style address."""
        try:
            if isinstance(addr, (tuple, list)) and len(addr) >= 1:
                return str(addr[0])
            return str(addr)
        except Exception:
            return ""

    def _is_allowed(host: str) -> bool:
        """Check whether a host is permitted by the current network policy."""
        h = _normalize_host(host)
        if h in _METADATA_HOSTS:
            return False
        if allow_localhost and h in _LOCALHOST:
            return True
        return any(_domain_matches(h, d) for d in allowed)

    def _bind_allowed(address: Any) -> bool:
        """Allow only loopback-style bind targets."""
        # Permit binding only to the loopback interface (or wildcard, which
        # we treat as loopback when allow_localhost is set). Inbound listeners
        # on a real interface let an attacker exfiltrate by waiting for a
        # peer to connect in.
        host = _host_from(address)
        h = _normalize_host(host)
        if not h:
            return True  # ephemeral / abstract namespace; let it through
        if h in _LOCALHOST:
            return True
        return False

    _socket_base: Any = _originals["socket_cls"]

    class GuardedSocket(_socket_base):  # type: ignore[misc]
        """Socket subclass that enforces the active network policy."""

        def connect(self, address: Any) -> Any:
            """Permit allowed outbound connections and reject the rest."""
            host = _host_from(address)
            if _is_allowed(host):
                return super().connect(address)
            _trace(f"blocked socket.connect host={host} reason=no-network")
            raise PolicyViolation(f"network disabled: connect({host})")

        def connect_ex(self, address: Any) -> int:
            """Mirror `connect_ex` while denying disallowed destinations."""
            host = _host_from(address)
            if _is_allowed(host):
                return int(super().connect_ex(address))
            _trace(f"blocked socket.connect_ex host={host} reason=no-network")
            return errno.EACCES

        def sendto(self, data: Any, address: Any) -> Any:
            """Permit datagram sends only to allowed destinations."""
            host = _host_from(address)
            if _is_allowed(host):
                return super().sendto(data, address)
            _trace(f"blocked socket.sendto host={host} reason=no-network")
            raise PolicyViolation(f"network disabled: sendto({host})")

        def bind(self, address: Any) -> Any:
            """Permit binds only on loopback-style interfaces."""
            if _bind_allowed(address):
                return super().bind(address)
            host = _host_from(address)
            _trace(f"blocked socket.bind host={host} reason=no-network")
            raise PolicyViolation(f"network disabled: bind({host})")

        if hasattr(_socket_base, "sendmsg"):

            def sendmsg(
                self,
                buffers: Any,
                ancdata: Any = (),
                flags: int = 0,
                address: Any = None,
            ) -> Any:
                """Permit `sendmsg` only for allowed destinations."""
                host = _host_from(address)
                if _is_allowed(host):
                    return super().sendmsg(buffers, ancdata, flags, address)
                _trace(f"blocked socket.sendmsg host={host} reason=no-network")
                raise PolicyViolation(f"network disabled: sendmsg({host})")

    def create_connection_guard(address: Any, *a: Any, **k: Any) -> Any:
        """Guard `socket.create_connection` with the active network policy."""
        host = _host_from(address)
        if _is_allowed(host):
            return _originals["create_connection"](address, *a, **k)
        _trace(f"blocked socket.create_connection host={host} reason=no-network")
        raise PolicyViolation(f"network disabled: create_connection({host})")

    def getaddrinfo_guard(host: Any, *a: Any, **k: Any) -> Any:
        """Guard DNS resolution through `socket.getaddrinfo`."""
        if _is_allowed(str(host)):
            return _originals["getaddrinfo"](host, *a, **k)
        _trace(f"blocked socket.getaddrinfo host={host} reason=no-network")
        raise PolicyViolation(f"network disabled: DNS({host})")

    def gethostbyname_guard(host: Any, *a: Any, **k: Any) -> Any:
        """Guard `socket.gethostbyname` lookups."""
        if _is_allowed(str(host)):
            return _originals["gethostbyname"](host, *a, **k)
        _trace(f"blocked socket.gethostbyname host={host} reason=no-network")
        raise PolicyViolation(f"network disabled: DNS({host})")

    def gethostbyname_ex_guard(host: Any, *a: Any, **k: Any) -> Any:
        """Guard `socket.gethostbyname_ex` lookups."""
        if _is_allowed(str(host)):
            return _originals["gethostbyname_ex"](host, *a, **k)
        _trace(f"blocked socket.gethostbyname_ex host={host} reason=no-network")
        raise PolicyViolation(f"network disabled: DNS({host})")

    def wrap_socket_guard(self: Any, sock: Any, *a: Any, **k: Any) -> Any:
        """Reject TLS wrapping that could hide outbound socket use."""
        # pylint: disable=unused-argument
        _trace("blocked ssl.SSLContext.wrap_socket reason=no-network")
        raise PolicyViolation("network disabled: TLS")

    def socketpair_guard(*a: Any, **k: Any) -> Any:  # pylint: disable=unused-argument
        """Reject creation of socketpair IPC channels."""
        # socketpair creates an in-process bidirectional channel. Block by
        # default — anything legitimately needing IPC can use a Pipe or Queue.
        _trace("blocked socket.socketpair reason=no-network")
        raise PolicyViolation("network disabled: socketpair")

    def fromfd_guard(*a: Any, **k: Any) -> Any:  # pylint: disable=unused-argument
        """Reject reconstruction of sockets from file descriptors."""
        # Reconstructing a socket from a leaked fd bypasses our class. Block.
        _trace("blocked socket.fromfd reason=no-network")
        raise PolicyViolation("network disabled: fromfd")

    def fromshare_guard(*a: Any, **k: Any) -> Any:  # pylint: disable=unused-argument
        """Reject reconstruction of sockets from shared state."""
        _trace("blocked socket.fromshare reason=no-network")
        raise PolicyViolation("network disabled: fromshare")

    socket.socket = GuardedSocket  # type: ignore[misc]
    if getattr(socket, "SocketType", None) is not None:
        socket.SocketType = GuardedSocket
    socket.create_connection = create_connection_guard
    socket.getaddrinfo = getaddrinfo_guard
    socket.gethostbyname = gethostbyname_guard
    socket.gethostbyname_ex = gethostbyname_ex_guard
    ssl.SSLContext.wrap_socket = wrap_socket_guard  # type: ignore[method-assign]
    if "socketpair" in _originals:
        socket.socketpair = socketpair_guard
    if "fromfd" in _originals:
        socket.fromfd = fromfd_guard
    if "fromshare" in _originals and hasattr(socket, "fromshare"):
        socket.fromshare = fromshare_guard
    # NOTE on _socket: we deliberately do NOT replace _socket.socket.
    # socket.socket inherits from _socket.socket, so swapping the C base
    # class causes infinite recursion in socket.socket.__init__. The
    # bypass remains: code that does `_socket.socket(...)` directly
    # avoids GuardedSocket. That's a known limitation documented in
    # spec/secure_secure.md — the surrounding network functions
    # (getaddrinfo, create_connection, gethostbyname) are all still
    # patched, so the attacker also has to do their own DNS, which we
    # block.


def uninstall() -> None:
    """Restore the original networking APIs."""
    global _installed
    if not _installed:
        return
    socket.socket = _originals["socket_cls"]  # type: ignore[misc]
    if _originals.get("SocketType") is not None:
        socket.SocketType = _originals["SocketType"]
    socket.create_connection = _originals["create_connection"]
    socket.getaddrinfo = _originals["getaddrinfo"]
    socket.gethostbyname = _originals["gethostbyname"]
    socket.gethostbyname_ex = _originals["gethostbyname_ex"]
    ssl.SSLContext.wrap_socket = _originals["wrap_socket"]  # type: ignore
    if "socketpair" in _originals:
        socket.socketpair = _originals["socketpair"]
    if "fromfd" in _originals:
        socket.fromfd = _originals["fromfd"]
    if "fromshare" in _originals and hasattr(socket, "fromshare"):
        socket.fromshare = _originals["fromshare"]
    _originals.clear()
    _installed = False


# --- Code for bootstrap.py generation ---
BOOTSTRAP_CODE = dedent(
    r"""
# --- network ---
if cfg.get("no_network"):
    _orig_socket = socket.socket
    _orig_socket_type = getattr(socket, "SocketType", None)
    _orig_create_connection = socket.create_connection
    _orig_getaddrinfo = socket.getaddrinfo
    _orig_gethostbyname = socket.gethostbyname
    _orig_gethostbyname_ex = socket.gethostbyname_ex
    _orig_wrap_socket = ssl.SSLContext.wrap_socket
    if hasattr(socket, "socketpair"):
        _orig_socketpair = socket.socketpair
    if hasattr(socket, "fromfd"):
        _orig_fromfd = socket.fromfd
    if hasattr(socket, "fromshare"):
        _orig_fromshare = socket.fromshare

    ALLOW_LOCAL = bool(cfg.get("allow_localhost"))
    ALLOW_DOMAINS = set([d.lower() for d in cfg.get("allow_domains", []) if d])
    META = {
        "169.254.169.254",
        "metadata.google.internal",
        "metadata",
        "fd00:ec2::254",
        "fd00:ec2:0:0:0:0:0:254",
        "fe80::a9fe:a9fe",
        "100.100.100.200",
    }
    LOCAL = {"127.0.0.1","::1","localhost","0.0.0.0"} # nosec

    def _host_from(addr):
        try:
            if isinstance(addr, (tuple, list)) and len(addr) >= 1: return str(addr[0])
            return str(addr)
        except Exception: return ""

    def _norm_host(host): return (host or "").strip().lower().rstrip(".")
    def _domain_match(host, domain):
        h, d = _norm_host(host), _norm_host(domain)
        return bool(d) and (h == d or h.endswith("." + d))

    def _is_net_allowed(host:str)->bool:
        h = _norm_host(host)
        if h in META: return False
        if ALLOW_LOCAL and h in LOCAL: return True
        return any(_domain_match(h, d) for d in ALLOW_DOMAINS)

    def _bind_allowed(address):
        host = _host_from(address)
        h = _norm_host(host)
        if not h: return True
        if h in LOCAL: return True
        return False

    class GuardedSocket(_orig_socket):
        def connect(self, address):
            host = _host_from(address)
            if _is_net_allowed(host): return super().connect(address)
            _tr(f"blocked socket.connect host={host}"); raise _HPolicy("network disabled")
        def connect_ex(self, address):
            host = _host_from(address)
            if _is_net_allowed(host): return super().connect_ex(address)
            _tr(f"blocked socket.connect_ex host={host}"); return errno.EACCES
        def sendto(self, data, address):
            host = _host_from(address)
            if _is_net_allowed(host): return super().sendto(data, address)
            _tr(f"blocked socket.sendto host={host}"); raise _HPolicy("network disabled")
        def bind(self, address):
            if _bind_allowed(address): return super().bind(address)
            host = _host_from(address)
            _tr(f"blocked socket.bind host={host}"); raise _HPolicy("network disabled")
        if hasattr(_orig_socket, "sendmsg"):
            def sendmsg(self, buffers, ancdata=(), flags=0, address=None):
                host = _host_from(address)
                if _is_net_allowed(host): return super().sendmsg(buffers, ancdata, flags, address)
                _tr(f"blocked socket.sendmsg host={host}"); raise _HPolicy("network disabled")

    def _guard_create_connection(addr, *a, **k):
        host = _host_from(addr)
        if _is_net_allowed(host): return _orig_create_connection(addr, *a, **k)
        _tr(f"blocked socket.create_connection host={host}"); raise _HPolicy("network disabled")

    def _guard_getaddrinfo(host, *a, **k):
        if _is_net_allowed(str(host)): return _orig_getaddrinfo(host, *a, **k)
        _tr(f"blocked socket.getaddrinfo host={host}"); raise _HPolicy("network disabled")

    def _guard_gethostbyname(host, *a, **k):
        if _is_net_allowed(str(host)): return _orig_gethostbyname(host, *a, **k)
        _tr(f"blocked socket.gethostbyname host={host}"); raise _HPolicy("network disabled")

    def _guard_gethostbyname_ex(host, *a, **k):
        if _is_net_allowed(str(host)): return _orig_gethostbyname_ex(host, *a, **k)
        _tr(f"blocked socket.gethostbyname_ex host={host}"); raise _HPolicy("network disabled")

    def _guard_wrap_socket(self, sock, *a, **k):
        _tr("blocked ssl.wrap_socket"); raise _HPolicy("network disabled")

    def _guard_socketpair(*a, **k):
        _tr("blocked socket.socketpair"); raise _HPolicy("network disabled")

    def _guard_fromfd(*a, **k):
        _tr("blocked socket.fromfd"); raise _HPolicy("network disabled")

    def _guard_fromshare(*a, **k):
        _tr("blocked socket.fromshare"); raise _HPolicy("network disabled")

    socket.socket = GuardedSocket
    if _orig_socket_type is not None:
        socket.SocketType = GuardedSocket
    socket.create_connection = _guard_create_connection
    socket.getaddrinfo = _guard_getaddrinfo
    socket.gethostbyname = _guard_gethostbyname
    socket.gethostbyname_ex = _guard_gethostbyname_ex
    ssl.SSLContext.wrap_socket = _guard_wrap_socket
    if hasattr(socket, "socketpair"):
        socket.socketpair = _guard_socketpair
    if hasattr(socket, "fromfd"):
        socket.fromfd = _guard_fromfd
    if hasattr(socket, "fromshare"):
        socket.fromshare = _guard_fromshare
"""
)
