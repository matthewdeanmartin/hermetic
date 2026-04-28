# tests/test_guards/test_network.py
import socket
import threading

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.network import install, uninstall


def test_network_guard():
    install(allow_localhost=True, allow_domains=["example.com"], trace=True)
    try:
        sock = socket.socket()
        sock.connect(("example.com", 80))  # Allowed
        with pytest.raises(PolicyViolation, match="network disabled: connect"):
            sock.connect(("google.com", 80))
    finally:
        uninstall()


def test_network_guard_blocks_raw_socket_aliases():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()
    accepted = threading.Event()

    def accept_once():
        try:
            conn, _addr = server.accept()
            conn.close()
            accepted.set()
        except OSError:
            pass
        finally:
            server.close()

    thread = threading.Thread(target=accept_once, daemon=True)
    thread.start()

    install(allow_localhost=False, allow_domains=[], trace=True)
    try:
        assert socket.SocketType is socket.socket

        with pytest.raises(PolicyViolation, match="network disabled: connect"):
            blocked = socket.socket()
            try:
                blocked.connect((host, port))
            finally:
                blocked.close()

        with pytest.raises(PolicyViolation, match="network disabled: connect"):
            blocked = socket.SocketType()
            try:
                blocked.connect((host, port))
            finally:
                blocked.close()
    finally:
        uninstall()
        server.close()
        thread.join(timeout=1)
        assert not accepted.is_set()
