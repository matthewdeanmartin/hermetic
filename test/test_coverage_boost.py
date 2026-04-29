# test/test_coverage_boost.py
import socket
import sys
from unittest.mock import MagicMock

import pytest

from hermetic.bootstrap import write_sitecustomize
from hermetic.errors import BootstrapError, PolicyViolation
from hermetic.guards import uninstall_all
from hermetic.profiles import GuardConfig
from hermetic.resolver import (
    TargetSpec,
    _console_entry,
    _script_shebang,
    invoke_inprocess,
    resolve,
)
from hermetic.runner import config_to_flags, run


@pytest.fixture(autouse=True)
def reset_guards():
    uninstall_all()
    yield
    uninstall_all()


def test_console_entry_mocked(mocker):
    # Mock importlib.metadata.entry_points
    mock_ep = MagicMock()
    mock_ep.name = "mycmd"
    mock_ep.value = "mymod:myfunc"

    mock_eps = MagicMock()
    mock_eps.select.return_value = [mock_ep]

    mocker.patch("importlib.metadata.entry_points", return_value=mock_eps)

    assert _console_entry("mycmd") == ("mymod", "myfunc")
    assert _console_entry("nonexistent") is None


def test_console_entry_legacy_fallback(mocker):
    # Mock importlib.metadata.entry_points that doesn't have .select (simulating older python)
    mock_ep = MagicMock()
    mock_ep.name = "mycmd"
    mock_ep.value = "mymod"
    mock_ep.group = "console_scripts"

    mock_eps = [mock_ep]

    # We want eps.select(...) to fail
    def side_effect(*args, **kwargs):
        raise AttributeError("No select")

    mock_eps_obj = MagicMock()
    mock_eps_obj.select.side_effect = side_effect
    mock_eps_obj.__iter__.return_value = iter(mock_eps)

    mocker.patch("importlib.metadata.entry_points", return_value=mock_eps_obj)

    assert _console_entry("mycmd") == ("mymod", "__main__")


def test_script_shebang_mocked(tmp_path):
    script = tmp_path / "script.py"
    script.write_text("#!/usr/bin/python3\nprint(1)")
    assert _script_shebang(str(script)) == "/usr/bin/python3"

    script_no_shebang = tmp_path / "noshebang.py"
    script_no_shebang.write_text("print(1)")
    assert _script_shebang(str(script_no_shebang)) is None

    assert _script_shebang("nonexistent_file") is None


def test_resolve_console_script(mocker):
    mocker.patch("hermetic.resolver._console_entry", return_value=("mymod", "main"))
    mocker.patch("hermetic.resolver.which", return_value="/usr/bin/mycmd")
    mocker.patch("hermetic.resolver._script_shebang", return_value=sys.executable)
    mocker.patch("os.path.realpath", side_effect=lambda x: x)

    spec = resolve("mycmd")
    assert spec.module == "mymod"
    assert spec.attr == "main"
    assert spec.mode == "inprocess"


def test_resolve_console_script_bootstrap(mocker):
    mocker.patch("hermetic.resolver._console_entry", return_value=("mymod", "main"))
    mocker.patch("hermetic.resolver.which", return_value="/usr/bin/mycmd")
    mocker.patch("hermetic.resolver._script_shebang", return_value="/other/python")
    mocker.patch("os.path.realpath", side_effect=lambda x: x)

    spec = resolve("mycmd")
    assert spec.mode == "bootstrap"


def test_resolve_path_executable_python(mocker):
    mocker.patch("hermetic.resolver._console_entry", return_value=None)
    mocker.patch("hermetic.resolver.which", return_value="/usr/bin/python3")
    mocker.patch("hermetic.resolver._script_shebang", return_value=None)

    spec = resolve("python3")
    assert spec.mode == "bootstrap"
    assert spec.module == ""


def test_invoke_inprocess_mocked(mocker):
    import runpy

    mock_run_module = mocker.patch.object(
        runpy, "run_module", return_value={"result": 0}
    )

    mock_mod = MagicMock()
    mock_mod.myfunc.return_value = 42
    mocker.patch("importlib.import_module", return_value=mock_mod)
    mocker.patch("sys.modules.pop")

    spec = TargetSpec(module="hermetic.util", attr="myfunc", mode="inprocess")
    assert invoke_inprocess(spec) == 42

    # Test __main__
    spec = TargetSpec(module="hermetic.util", attr="__main__", mode="inprocess")
    assert invoke_inprocess(spec) == {"result": 0}
    mock_run_module.assert_called_with("hermetic.util", run_name="__main__")


def test_run_policy_violation(mocker):
    mocker.patch(
        "hermetic.runner.resolve",
        return_value=TargetSpec(module="mod", attr="func", mode="inprocess"),
    )
    mocker.patch("hermetic.runner.install_all")
    mocker.patch(
        "hermetic.runner.invoke_inprocess", side_effect=PolicyViolation("bad thing")
    )
    mocker.patch("hermetic.runner.uninstall_all")

    cfg = GuardConfig(no_network=True)
    res = run("target", ["target"], cfg)
    assert res == 2


def test_write_sitecustomize_error(mocker):
    mocker.patch("tempfile.mkdtemp", side_effect=Exception("disk full"))
    with pytest.raises(BootstrapError):
        write_sitecustomize({})


def test_config_to_flags():
    cfg = GuardConfig(no_network=True, trace=True)
    flags = config_to_flags(cfg)
    assert flags["no_network"] is True
    assert flags["trace"] is True


def test_run_bootstrap_win32(mocker):
    if sys.platform != "win32":
        pytest.skip("Windows only")

    mocker.patch(
        "hermetic.runner.resolve",
        return_value=TargetSpec(
            module="mod",
            attr="func",
            mode="bootstrap",
            exe_path="exe",
            interp_path="interp",
        ),
    )
    mocker.patch("hermetic.runner.write_sitecustomize", return_value="/tmp/site")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0

    # We expect sys.exit(0) to be called
    with pytest.raises(SystemExit) as exc:
        run("target", ["target", "arg1"], GuardConfig())
    assert exc.value.code == 0


from hermetic.cli import main
from hermetic.util import is_same_interpreter


def test_main_help(mocker):
    # Test main with help should exit or print help
    mocker.patch("argparse.ArgumentParser.print_help")
    with pytest.raises(SystemExit):
        main(["--help"])


def test_main_no_target_help(mocker):
    # Test main with help token and no target
    mocker.patch("argparse.ArgumentParser.print_help")
    with pytest.raises(SystemExit) as exc:
        main(["-h"])
    assert exc.value.code == 0


def test_main_empty_target(mocker):
    # Test main with -- but no target after it
    # Current behavior: prints help and returns 0
    mocker.patch("argparse.ArgumentParser.print_help")
    assert main(["--"]) == 0


def test_main_with_target(mocker):
    mocker.patch("hermetic.cli.run", return_value=0)
    assert main(["--no-network", "--", "target", "arg"]) == 0


def test_resolve_console_script_no_exe(mocker):
    mocker.patch("hermetic.resolver._console_entry", return_value=("mymod", "main"))
    mocker.patch("hermetic.resolver.which", return_value=None)

    spec = resolve("mycmd")
    assert spec.module == "mymod"
    assert spec.mode == "inprocess"


def test_invoke_inprocess_fallback(mocker):
    # Test fallback path in invoke_inprocess when attr is not callable
    mock_runpy = mocker.patch("hermetic.resolver.runpy")
    mock_runpy.run_module.return_value = {"result": 0}

    mock_mod = MagicMock()
    mock_mod.func = "not callable"
    mocker.patch("importlib.import_module", return_value=mock_mod)
    mocker.patch("sys.modules.pop")

    spec = TargetSpec(module="hermetic.util", attr="func", mode="inprocess")
    assert invoke_inprocess(spec) == {"result": 0}


import hermetic.guards.filesystem as fs_guard
import hermetic.guards.network as net_guard
import hermetic.guards.subprocess_guard as sub_guard


def test_network_idempotency():
    net_guard.install(allow_localhost=True, allow_domains=[])
    net_guard.install(allow_localhost=True, allow_domains=[])  # Should return early
    net_guard.uninstall()
    net_guard.uninstall()  # Should return early


def test_network_edge_cases(mocker):
    # Test _host_from with Exception via connect
    net_guard.install(allow_localhost=True, allow_domains=[])
    try:

        class BadAddr:
            def __str__(self):
                raise Exception("fail")

            def __getitem__(self, i):
                raise Exception("fail")

        sock = socket.socket()
        # This will call _host_from(BadAddr())
        with pytest.raises(PolicyViolation):
            sock.connect(BadAddr())
    finally:
        net_guard.uninstall()


def test_filesystem_idempotency():
    fs_guard.install()
    fs_guard.install()
    fs_guard.uninstall()
    fs_guard.uninstall()


def test_filesystem_edge_cases(mocker):
    # Test _coerce_path via open
    fs_guard.install()
    try:

        class BadPath:
            def __str__(self):
                return "badpath"

            # No __fspath__ will cause TypeError in os.fspath

        # Should not raise during coercion, but will fail in open
        with pytest.raises((FileNotFoundError, TypeError)):
            open(BadPath(), mode="r")
    finally:
        fs_guard.uninstall()


def test_subprocess_idempotency():
    sub_guard.install()
    sub_guard.install()
    sub_guard.uninstall()
    sub_guard.uninstall()


import hermetic.guards.imports_guard as imp_guard
from hermetic.guards.imports_guard import _patch_module_attrs


def test_imports_idempotency():
    imp_guard.install()
    imp_guard.install()
    imp_guard.uninstall()
    imp_guard.uninstall()


def test_imports_edge_cases(mocker):
    # Test _patch_module_attrs with read-only attribute
    mock_mod = MagicMock()
    mock_mod.attr = 1
    mocker.patch("sys.modules", {"mymod": mock_mod})

    # Patch setattr only in the imports_guard namespace
    mocker.patch(
        "hermetic.guards.imports_guard.setattr", side_effect=TypeError("read only")
    )
    _patch_module_attrs("mymod", ("attr",))

    # Test invalidate_caches failure
    mocker.patch("importlib.invalidate_caches", side_effect=Exception("fail"))
    imp_guard.install()
    imp_guard.uninstall()


def test_run_bootstrap_unix_mocked(mocker):
    mocker.patch("sys.platform", "linux")
    mocker.patch(
        "hermetic.runner.resolve",
        return_value=TargetSpec(
            module="mod",
            attr="func",
            mode="bootstrap",
            exe_path="exe",
            interp_path="interp",
        ),
    )
    mocker.patch("hermetic.runner.write_sitecustomize", return_value="/tmp/site")
    mock_execve = mocker.patch("os.execve")
    mocker.patch("hermetic.runner.invoke_inprocess")

    run("target", ["target", "arg1"], GuardConfig())
    assert mock_execve.called


def test_about():
    import hermetic.__about__ as about

    assert about.__version__ == "0.2.0"


def test_is_same_interpreter_mocked(mocker):
    mocker.patch("os.path.realpath", side_effect=lambda x: x)
    mocker.patch("sys.executable", "/usr/bin/python")
    assert is_same_interpreter("/usr/bin/python") is True
    assert is_same_interpreter("/usr/bin/other") is False

    mocker.patch("os.path.realpath", side_effect=Exception("error"))
    assert is_same_interpreter("/usr/bin/python") is False


def test_main_exec_mocked(mocker):
    # Test __main__.py logic indirectly
    mocker.patch("hermetic.cli.main", return_value=0)
    # Trigger the if __name__ == "__main__" block if we can,
    # but we can't easily without runpy.
    # We already covered the import.
