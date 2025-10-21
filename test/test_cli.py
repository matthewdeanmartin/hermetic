# tests/test_cli.py


from hermetic.cli import parse_hermetic_args
from hermetic.profiles import GuardConfig


# def test_build_parser():
#     parser = build_parser()
#     assert isinstance(parser, argparse.ArgumentParser)
#     args = parser.parse_args(["--no-network", "--allow-localhost", "--"])
#     assert args.no_network is True
#     assert args.allow_localhost is True
#
def test_parse_hermetic_args():
    argv = ["--no-network", "--no-subprocess", "--allow-domain=example.com", "--trace"]
    cfg = parse_hermetic_args(argv)
    assert cfg == GuardConfig(
        no_network=True,
        no_subprocess=True,
        fs_readonly=False,
        fs_root=None,
        block_native=False,
        allow_localhost=False,
        allow_domains=["example.com"],
        trace=True,
    )


def test_parse_hermetic_args_with_profile():
    argv = ["--profile=net-hermetic", "--no-subprocess"]
    cfg = parse_hermetic_args(argv)
    assert cfg.no_network is True
    assert cfg.allow_localhost is True
    assert cfg.no_subprocess is True


# def test_main_help(capsys):
#     exit_code = main(["--help"])
#     # assert exit_code == 0
#     captured = capsys.readouterr()
#     assert "Run a Python console script with user-space sandbox guards." in captured.out
#
# def test_main_missing_target():
#     main(["--no-network", "--"])
