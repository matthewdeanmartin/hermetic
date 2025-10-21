# tests/test_guards/test_network.py
import socket

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
