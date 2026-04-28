"""Phase 2 hardening tests: socketpair, fromfd, bind, IPv6 metadata."""
from __future__ import annotations

import socket

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.network import install, uninstall


def test_socketpair_blocked():
    install(allow_localhost=False, allow_domains=[], trace=False)
    try:
        with pytest.raises(PolicyViolation, match="socketpair"):
            socket.socketpair()
    finally:
        uninstall()


def test_fromfd_blocked():
    if not hasattr(socket, "fromfd"):
        pytest.skip("socket.fromfd not available on this platform")
    install(allow_localhost=False, allow_domains=[], trace=False)
    try:
        with pytest.raises(PolicyViolation, match="fromfd"):
            socket.fromfd(0, socket.AF_INET, socket.SOCK_STREAM)
    finally:
        uninstall()


def test_bind_to_external_blocked():
    install(allow_localhost=True, allow_domains=[], trace=False)
    try:
        s = socket.socket()
        try:
            with pytest.raises(PolicyViolation, match="bind"):
                # 192.0.2.1 is TEST-NET-1: guaranteed not to route. We just
                # want the policy refusal before the syscall.
                s.bind(("192.0.2.1", 0))
        finally:
            s.close()
    finally:
        uninstall()


def test_bind_to_loopback_allowed():
    install(allow_localhost=True, allow_domains=[], trace=False)
    try:
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", 0))  # should succeed
        finally:
            s.close()
    finally:
        uninstall()


def test_ipv6_metadata_denied():
    install(allow_localhost=False, allow_domains=["fd00:ec2::254"], trace=False)
    try:
        # Even when explicitly allow-listed, metadata hosts stay denied.
        with pytest.raises(PolicyViolation, match="DNS"):
            socket.getaddrinfo("fd00:ec2::254", 80)
    finally:
        uninstall()
