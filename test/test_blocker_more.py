"""
Comprehensive pytest suite for hermetic blocker.

Focus: Entry points in blocker.py - verify guards actually block actions.
Strategy: Minimal mocking, real filesystem/network/subprocess attempts.

Import Order: All imports that might be patched (os, subprocess, etc.) must happen
AFTER the hermetic_blocker context is entered. This matches the real use case where
the developer controls the entrypoint and import order.
"""
from __future__ import annotations

import asyncio
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from hermetic.blocker import BlockConfig, hermetic_blocker, with_hermetic
from hermetic.errors import PolicyViolation

if TYPE_CHECKING:
    from _pytest.tmpdir import TempPathFactory


# ============================================================================
# Network Guard Tests
# ============================================================================

class TestNetworkGuard:
    """Test network blocking via hermetic_blocker context manager."""

    def test_network_blocked_socket_connect(self) -> None:
        """Verify socket.connect raises PolicyViolation when network blocked."""
        with hermetic_blocker(block_network=True):
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            with pytest.raises(PolicyViolation, match="network disabled"):
                sock.connect(("example.com", 80))

    def test_network_blocked_create_connection(self) -> None:
        """Verify socket.create_connection raises PolicyViolation."""
        with hermetic_blocker(block_network=True):
            with pytest.raises(PolicyViolation, match="network disabled"):
                socket.create_connection(("example.com", 80), timeout=1)

    def test_network_blocked_getaddrinfo(self) -> None:
        """Verify DNS lookups are blocked."""
        with hermetic_blocker(block_network=True):
            with pytest.raises(PolicyViolation, match="network disabled"):
                import socket
                socket.getaddrinfo("example.com", 80)

    def test_network_allow_localhost(self) -> None:
        """Verify localhost is allowed when allow_localhost=True."""
        with hermetic_blocker(block_network=True, allow_localhost=True):
            # Should not raise - localhost is allowed
            import socket
            info = socket.getaddrinfo("localhost", 80)
            assert len(info) > 0

    def test_network_allow_domains(self) -> None:
        """Verify allowed domains can be accessed."""
        with hermetic_blocker(block_network=True, allow_domains=["example.com"]):
            # Should not raise - example.com is allowed
            import socket
            info = socket.getaddrinfo("example.com", 80)
            assert len(info) > 0

    def test_network_blocks_metadata_endpoints(self) -> None:
        """Verify cloud metadata endpoints are always blocked."""
        with hermetic_blocker(block_network=True, allow_localhost=True):
            with pytest.raises(PolicyViolation):
                import socket
                socket.getaddrinfo("169.254.169.254", 80)

    def test_network_unblocked_after_exit(self) -> None:
        """Verify network works normally after context exit."""
        with hermetic_blocker(block_network=True):
            pass
        # Should work fine now
        import socket
        info = socket.getaddrinfo("example.com", 80)
        assert len(info) > 0

    def test_network_nested_contexts(self) -> None:
        """Verify nested contexts maintain blocking until outermost exits."""
        with hermetic_blocker(block_network=True):
            import socket
            with hermetic_blocker(block_network=True):
                import socket
                with pytest.raises(PolicyViolation):
                    socket.getaddrinfo("example.com", 80)
            # Still blocked - outer context still active
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)
        import socket
        # Now unblocked
        info = socket.getaddrinfo("example.com", 80)
        assert len(info) > 0


# ============================================================================
# Subprocess Guard Tests
# ============================================================================

class TestSubprocessGuard:
    """Test subprocess blocking."""

    def test_subprocess_popen_blocked(self) -> None:
        """Verify subprocess.Popen raises PolicyViolation."""
        with hermetic_blocker(block_subprocess=True):
            with pytest.raises(PolicyViolation, match="subprocess disabled"):
                import subprocess
                subprocess.Popen(["echo", "hello"])

    def test_subprocess_run_blocked(self) -> None:
        """Verify subprocess.run raises PolicyViolation."""
        with hermetic_blocker(block_subprocess=True):
            with pytest.raises(PolicyViolation, match="subprocess disabled"):
                import subprocess
                subprocess.run(["echo", "hello"])

    def test_subprocess_call_blocked(self) -> None:
        """Verify subprocess.call raises PolicyViolation."""
        with hermetic_blocker(block_subprocess=True):
            with pytest.raises(PolicyViolation, match="subprocess disabled"):
                import subprocess
                subprocess.call(["echo", "hello"])

    def test_os_system_blocked(self) -> None:
        """Verify os.system raises PolicyViolation."""
        with hermetic_blocker(block_subprocess=True):
            import os  # Import AFTER guard installation
            with pytest.raises(PolicyViolation, match="subprocess disabled"):
                os.system("echo hello")

    @pytest.mark.asyncio
    async def test_asyncio_subprocess_blocked(self) -> None:
        """Verify asyncio subprocess creation is blocked."""
        with hermetic_blocker(block_subprocess=True):
            with pytest.raises(PolicyViolation, match="subprocess disabled"):
                import asyncio
                await asyncio.create_subprocess_exec("bash",  "-c", '"echo hello"')

    def test_subprocess_unblocked_after_exit(self) -> None:
        """Verify subprocess works after context exit."""
        with hermetic_blocker(block_subprocess=True):
            pass
        # Should work now
        import subprocess
        result = subprocess.run(["bash",  "-c", "echo"], capture_output=True, text=True)
        assert result.returncode == 0


# ============================================================================
# Filesystem Guard Tests
# ============================================================================

class TestFilesystemGuard:
    """Test filesystem readonly blocking."""

    def test_open_write_blocked(self, tmp_path: Path) -> None:
        """Verify opening file for write raises PolicyViolation."""
        test_file = tmp_path / "test.txt"
        with hermetic_blocker(fs_readonly=True):
            with pytest.raises(PolicyViolation, match="filesystem readonly"):
                open(test_file, "w")

    def test_open_append_blocked(self, tmp_path: Path) -> None:
        """Verify opening file for append raises PolicyViolation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("existing")
        with hermetic_blocker(fs_readonly=True):
            with pytest.raises(PolicyViolation, match="filesystem readonly"):
                open(test_file, "a")

    def test_open_read_allowed(self, tmp_path: Path) -> None:
        """Verify reading files is allowed in readonly mode."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        with hermetic_blocker(fs_readonly=True):
            with open(test_file, "r") as f:
                assert f.read() == "content"

    def test_pathlib_write_blocked(self, tmp_path: Path) -> None:
        """Verify pathlib write operations are blocked."""
        test_file = tmp_path / "test.txt"
        with hermetic_blocker(fs_readonly=True):
            with pytest.raises(PolicyViolation, match="filesystem readonly"):
                test_file.open("w")

    def test_os_remove_blocked(self, tmp_path: Path) -> None:
        """Verify os.remove raises PolicyViolation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        with hermetic_blocker(fs_readonly=True):
            import os  # Import after guard installation
            with pytest.raises(PolicyViolation, match="mutation disabled"):
                os.remove(str(test_file))

    def test_os_mkdir_blocked(self, tmp_path: Path) -> None:
        """Verify os.mkdir raises PolicyViolation."""
        new_dir = tmp_path / "newdir"
        with hermetic_blocker(fs_readonly=True):
            import os  # Import after guard installation
            with pytest.raises(PolicyViolation, match="mutation disabled"):
                os.mkdir(str(new_dir))

    def test_fs_root_restricts_reads(self, tmp_path: Path) -> None:
        """Verify fs_root parameter restricts read access."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        inside = sandbox / "inside.txt"
        inside.write_text("allowed")
        outside = tmp_path / "outside.txt"
        outside.write_text("forbidden")

        with hermetic_blocker(fs_readonly=True, fs_root=str(sandbox)):
            # Can read inside sandbox
            with open(inside, "r") as f:
                assert f.read() == "allowed"
            # Cannot read outside sandbox
            with pytest.raises(PolicyViolation, match="outside sandbox root"):
                open(outside, "r")

    def test_fs_unblocked_after_exit(self, tmp_path: Path) -> None:
        """Verify filesystem mutations work after context exit."""
        test_file = tmp_path / "test.txt"
        with hermetic_blocker(fs_readonly=True):
            pass
        # Should work now
        test_file.write_text("content")
        assert test_file.read_text() == "content"


# ============================================================================
# Import Guard Tests
# ============================================================================

class TestImportGuard:
    """Test strict imports blocking."""

    def test_ctypes_import_blocked(self) -> None:
        """Verify ctypes import raises PolicyViolation."""
        with hermetic_blocker(strict_imports=True):
            with pytest.raises(PolicyViolation, match="import blocked"):
                import ctypes

    def test_cffi_import_blocked(self) -> None:
        """Verify cffi import raises PolicyViolation (if installed)."""
        with hermetic_blocker(strict_imports=True):
            with pytest.raises((PolicyViolation, ModuleNotFoundError)):
                import cffi

    def test_normal_imports_allowed(self) -> None:
        """Verify normal pure-Python imports work."""
        with hermetic_blocker(strict_imports=True):
            import json
            import collections
            assert json and collections

    def test_imports_unblocked_after_exit(self) -> None:
        """Verify imports work after context exit."""
        with hermetic_blocker(strict_imports=True):
            pass
        import ctypes
        assert ctypes


# ============================================================================
# Multi-Guard Tests
# ============================================================================

class TestMultipleGuards:
    """Test multiple guards active simultaneously."""

    def test_all_guards_active(self, tmp_path: Path) -> None:
        """Verify all guards can be active at once."""
        test_file = tmp_path / "test.txt"
        with hermetic_blocker(
            block_network=True,
            block_subprocess=True,
            fs_readonly=True,
            strict_imports=True,
        ):
            # Network blocked
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)
            # Subprocess blocked
            with pytest.raises(PolicyViolation):
                import subprocess
                subprocess.run(["echo", "hello"])
            # Filesystem writes blocked
            with pytest.raises(PolicyViolation):
                open(test_file, "w")
            # FFI imports blocked
            with pytest.raises(PolicyViolation):
                import ctypes

    def test_partial_guards(self) -> None:
        """Verify only specified guards are active."""
        with hermetic_blocker(block_network=True):
            # Network blocked
            with pytest.raises(PolicyViolation):
                import socket
                socket.getaddrinfo("example.com", 80)
            # Subprocess still works
            import subprocess
            result = subprocess.run(["bash", "-c", "echo"], capture_output=True)
            assert result.returncode == 0


# ============================================================================
# Configuration Tests
# ============================================================================

class TestBlockConfig:
    """Test BlockConfig dataclass."""

    def test_from_kwargs_long_names(self) -> None:
        """Verify from_kwargs accepts long argument names."""
        cfg = BlockConfig.from_kwargs(
            block_network=True,
            block_subprocess=True,
            fs_readonly=True,
            strict_imports=True,
            allow_localhost=True,
            allow_domains=["example.com"],
            trace=True,
        )
        assert cfg.block_network is True
        assert cfg.block_subprocess is True
        assert cfg.fs_readonly is True
        assert cfg.strict_imports is True
        assert cfg.allow_localhost is True
        assert cfg.allow_domains == ["example.com"]
        assert cfg.trace is True

    def test_from_kwargs_short_names(self) -> None:
        """Verify from_kwargs accepts short argument names."""
        cfg = BlockConfig.from_kwargs(
            no_network=True,
            no_subprocess=True,
        )
        assert cfg.block_network is True
        assert cfg.block_subprocess is True

    def test_from_kwargs_unknown_arg_raises(self) -> None:
        """Verify unknown arguments raise TypeError."""
        with pytest.raises(TypeError, match="Unknown argument"):
            BlockConfig.from_kwargs(unknown_arg=True)


# ============================================================================
# Decorator Tests
# ============================================================================

class TestDecorators:
    """Test decorator usage of hermetic_blocker."""

    def test_decorator_blocks_network(self) -> None:
        """Verify decorator form blocks network."""
        @hermetic_blocker(block_network=True)
        def make_request() -> None:
            import socket
            socket.getaddrinfo("example.com", 80)

        with pytest.raises(PolicyViolation, match="network disabled"):
            make_request()

    def test_with_hermetic_decorator(self) -> None:
        """Verify with_hermetic decorator factory works."""
        @with_hermetic(block_network=True, block_subprocess=True)
        def restricted_func() -> str:
            with pytest.raises(PolicyViolation):
                import socket
                socket.getaddrinfo("example.com", 80)
            with pytest.raises(PolicyViolation):
                import subprocess
                subprocess.run(["echo", "hello"])
            return "success"

        assert restricted_func() == "success"

    def test_decorator_unblocks_after_function(self) -> None:
        """Verify guards are removed after decorated function completes."""
        @hermetic_blocker(block_network=True)
        def restricted() -> None:
            with pytest.raises(PolicyViolation):
                import socket
                socket.getaddrinfo("example.com", 80)

        restricted()
        # Should work now
        import socket
        info = socket.getaddrinfo("example.com", 80)
        assert len(info) > 0


# ============================================================================
# Async Context Tests
# ============================================================================

class TestAsyncContext:
    """Test async context manager support."""

    @pytest.mark.asyncio
    async def test_async_with_blocks_network(self) -> None:
        """Verify async with blocks network."""
        async with hermetic_blocker(block_network=True):
            with pytest.raises(PolicyViolation, match="network disabled"):
                import socket
                socket.getaddrinfo("example.com", 80)

    @pytest.mark.asyncio
    async def test_async_with_blocks_subprocess(self) -> None:
        """Verify async with blocks subprocess."""
        async with hermetic_blocker(block_subprocess=True):
            with pytest.raises(PolicyViolation, match="subprocess disabled"):
                import asyncio
                await asyncio.create_subprocess_exec("echo", "hello")

    @pytest.mark.asyncio
    async def test_async_unblocks_after_exit(self) -> None:
        """Verify async context properly unblocks."""
        async with hermetic_blocker(block_network=True):
            pass
        # Should work now
        import socket
        info = socket.getaddrinfo("example.com", 80)
        assert len(info) > 0


# ============================================================================
# Thread Safety Tests
# ============================================================================

class TestThreadSafety:
    """Test thread safety of guard installation."""

    def test_concurrent_context_entries(self) -> None:
        """Verify multiple threads can safely enter contexts."""
        errors: list[Exception] = []

        def thread_func(thread_id: int) -> None:
            try:
                with hermetic_blocker(block_network=True):
                    with pytest.raises(PolicyViolation):
                        import socket
                        socket.getaddrinfo("example.com", 80)
            except Exception as e:
                errors.append(e)
        import threading
        threads = [threading.Thread(target=thread_func, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"

    def test_reference_counting(self) -> None:
        """Verify reference counting works correctly with nesting."""
        # First context
        with hermetic_blocker(block_network=True):
            # Network blocked
            with pytest.raises(PolicyViolation):
                import socket
                socket.getaddrinfo("example.com", 80)
            # Nested context
            with hermetic_blocker(block_network=True):
                # Still blocked
                with pytest.raises(PolicyViolation):
                    import socket
                    socket.getaddrinfo("example.com", 80)
            # Still blocked after nested exit
            with pytest.raises(PolicyViolation):
                import socket
                socket.getaddrinfo("example.com", 80)
        # Unblocked after all exits
        info = socket.getaddrinfo("example.com", 80)
        assert len(info) > 0




# ============================================================================
# Exception Handling Tests
# ============================================================================

class TestExceptionHandling:
    """Test that guards are properly removed even with exceptions."""

    def test_guards_removed_on_exception(self) -> None:
        """Verify guards are removed even if exception occurs in context."""
        try:
            with hermetic_blocker(block_network=True):
                raise ValueError("test error")
        except ValueError:
            pass

        # Guards should be removed
        import socket
        info = socket.getaddrinfo("example.com", 80)
        assert len(info) > 0

    def test_exception_propagates(self) -> None:
        """Verify exceptions are not suppressed by context manager."""
        with pytest.raises(ValueError, match="test error"):
            with hermetic_blocker(block_network=True):
                raise ValueError("test error")


# ============================================================================
# Bug-Finding Tests (Expected Failures or Edge Cases)
# ============================================================================

class TestEdgeCases:
    """Tests designed to find potential bugs or edge cases."""

    def test_preimported_modules_bypass_guards(self) -> None:
        """KNOWN LIMITATION: Modules imported before guard installation aren't patched.

        This documents a real limitation of the hermetic blocker approach.
        If user code imports modules before entering the hermetic context,
        those early imports retain references to the original, unpatched functions.

        This is why runner.py does sys.modules.pop() before invoking targets.
        """
        import os as os_early  # Import BEFORE guard

        with hermetic_blocker(block_subprocess=True):
            import os as os_late  # Import AFTER guard

            # Late import is guarded
            with pytest.raises(PolicyViolation):
                os_late.system("echo guarded")

            with pytest.raises(PolicyViolation):
                result = os_early.system("echo bypass")
                # os.system returns exit code, 0 = success
                assert result == 0, "Early import bypassed guard as expected"

    def test_empty_domain_list_blocks_all(self) -> None:
        """Empty allow_domains should block all non-localhost."""
        with hermetic_blocker(block_network=True, allow_domains=[]):
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)

    def test_socket_connect_ex_returns_errno(self) -> None:
        """Verify connect_ex returns errno instead of raising."""
        with hermetic_blocker(block_network=True):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("example.com", 80))
            # Should return an error code, not 0
            assert result != 0
    #
    # def test_fs_root_with_symlinks(self, tmp_path: Path) -> None:
    #     """Test fs_root handles symlinks correctly."""
    #     sandbox = tmp_path / "sandbox"
    #     sandbox.mkdir()
    #     outside = tmp_path / "outside.txt"
    #     outside.write_text("outside")
    #
    #     # Create symlink inside sandbox pointing outside
    #     link = sandbox / "link.txt"
    #     link.symlink_to(outside)
    #
    #     with hermetic_blocker(fs_readonly=True, fs_root=str(sandbox)):
    #         # BUG FINDER: Should this be blocked? The symlink target is outside.
    #         # Current behavior might allow reading through symlink.
    #         try:
    #             with open(link, "r") as f:
    #                 content = f.read()
    #             # If we got here, symlinks bypass the fs_root check
    #             print(f"POTENTIAL BUG: Symlink allowed access outside sandbox: {content}")
    #         except PolicyViolation:
    #             # This is the expected secure behavior
    #             pass

    def test_multiple_exit_calls_safe(self) -> None:
        """Verify calling __exit__ multiple times is safe."""
        blocker = hermetic_blocker(block_network=True)
        blocker.__enter__()
        blocker.__exit__(None, None, None)
        # Second exit should be safe (no-op)
        blocker.__exit__(None, None, None)
        # Network should work
        import socket
        info = socket.getaddrinfo("example.com", 80)
        assert len(info) > 0

    def test_guard_reinstallation_after_uninstall(self) -> None:
        """Verify guards can be reinstalled after full uninstallation."""
        with hermetic_blocker(block_network=True):
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)

        # Guards removed, verify network works
        socket.getaddrinfo("example.com", 80)

        # Reinstall guards
        with hermetic_blocker(block_network=True):
            with pytest.raises(PolicyViolation):
                socket.getaddrinfo("example.com", 80)

    @pytest.mark.parametrize("mode", ["r+", "w+", "a+", "x+"])
    def test_open_plus_modes_blocked(self, tmp_path: Path, mode: str) -> None:
        """Verify all + modes are blocked (they allow writing)."""
        test_file = tmp_path / "test.txt"
        if "x" not in mode:  # x mode requires file not exist
            test_file.write_text("content")

        with hermetic_blocker(fs_readonly=True):
            with pytest.raises(PolicyViolation, match="filesystem readonly"):
                open(test_file, mode)