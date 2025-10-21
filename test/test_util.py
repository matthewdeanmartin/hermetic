# tests/test_util.py

import pytest

from hermetic.util import SplitArgs, split_argv


def test_split_argv_with_separator():
    argv = ["--no-network", "--", "target", "--arg"]
    result = split_argv(argv)
    assert result == SplitArgs(
        hermetic_argv=["--no-network"], target_argv=["target", "--arg"]
    )


def test_split_argv_help_tokens():
    argv = ["--no-network", "--help"]
    result = split_argv(argv)
    assert result == SplitArgs(hermetic_argv=["--no-network", "--help"], target_argv=[])


def test_split_argv_no_separator():
    argv = ["--no-network", "target"]
    with pytest.raises(
        SystemExit, match="usage error: separate hermetic and target args with `--`"
    ):
        split_argv(argv)


# def test_which(tmp_path):
#     script = tmp_path / "myscript"
#     script.write_text("content")
#     script.chmod(0o755)
#     os.environ["PATH"] = str(tmp_path)
#     assert which("myscript") == str(script)
