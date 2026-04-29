from __future__ import annotations

import os
import socket
import subprocess
import sys

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards import (
    code_exec,
    environment,
    filesystem,
    imports_guard,
    interpreter,
    network,
    subprocess_guard,
)


def _assert_stderr_only(capsys: pytest.CaptureFixture[str], expected: str) -> None:
    captured = capsys.readouterr()
    assert expected in captured.err
    assert captured.out == ""


def test_network_trace_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    network.install(allow_localhost=False, allow_domains=[], trace=True)
    try:
        with pytest.raises(PolicyViolation, match="DNS"):
            socket.getaddrinfo("example.com", 80)
        _assert_stderr_only(capsys, "blocked socket.getaddrinfo host=example.com")
    finally:
        network.uninstall()


def test_subprocess_trace_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    subprocess_guard.install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="subprocess disabled"):
            subprocess.run(["python", "-V"])
        _assert_stderr_only(capsys, "blocked subprocess reason=no-subprocess")
    finally:
        subprocess_guard.uninstall()


def test_filesystem_trace_goes_to_stderr(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    filesystem.install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="filesystem readonly"):
            open(tmp_path / "trace.txt", "w")
        _assert_stderr_only(capsys, "blocked open write")
    finally:
        filesystem.uninstall()


def test_environment_trace_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    environment.install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="environment disabled"):
            os.getenv("PATH")
        _assert_stderr_only(capsys, "blocked environment read")
    finally:
        environment.uninstall()


def test_code_exec_trace_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    code_exec.install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="eval"):
            eval("1 + 1")
        _assert_stderr_only(capsys, "blocked eval")
    finally:
        code_exec.uninstall()


def test_interpreter_trace_goes_to_stderr(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    interpreter.install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="sys.path"):
            sys.path.append(str(tmp_path))
        _assert_stderr_only(capsys, "blocked sys.path mutation")
    finally:
        interpreter.uninstall()


def test_import_trace_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    imports_guard.install(trace=True)
    try:
        with pytest.raises(PolicyViolation, match="import blocked: ctypes"):
            __import__("ctypes")
        _assert_stderr_only(capsys, "blocked import name=ctypes")
    finally:
        imports_guard.uninstall()
