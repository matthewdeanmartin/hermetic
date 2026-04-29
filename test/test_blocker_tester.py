from __future__ import annotations

import types

import pytest

from hermetic.blocker import BlockConfig, hermetic_blocker, with_hermetic


@pytest.fixture(autouse=True)
def reset_blocker_state(monkeypatch):
    """
    Ensure hermetic.blocker starts each test with clean global state and
    predictable guard stubs that *record* calls without performing real patches.
    """
    # Re-import to get the module; don't reload yet (we'll mutate state below).
    import hermetic.blocker as blocker

    # Reset lock-guarded policy state.
    blocker._ACTIVE_CONFIGS.clear()  # noqa: SLF001

    calls = {
        "install_all": [],
        "uninstall_all": [],
        "timeline": [],  # order assertions: "install", "func", "uninstall"
    }

    def _stub_install_all(
        *, net=None, subproc=None, fs=None, env=None, code=None, interp=None, imports=None
    ):
        calls["install_all"].append(
            dict(
                net=net,
                subproc=subproc,
                fs=fs,
                env=env,
                code=code,
                interp=interp,
                imports=imports,
            )
        )
        calls["timeline"].append("install")

    def _stub_uninstall_all():
        calls["uninstall_all"].append(True)
        calls["timeline"].append("uninstall")

    # Patch guards at the package import location the code uses.
    import hermetic.guards as guards  # package must exist in project

    monkeypatch.setattr(guards, "install_all", _stub_install_all, raising=True)
    monkeypatch.setattr(guards, "uninstall_all", _stub_uninstall_all, raising=True)

    # Also ensure blocker sees the patched names via its imports.
    monkeypatch.setattr(blocker, "install_all", _stub_install_all, raising=True)
    monkeypatch.setattr(blocker, "uninstall_all", _stub_uninstall_all, raising=True)

    # Provide test helper access
    yield types.SimpleNamespace(calls=calls, blocker=blocker)

    # Safety: if someone forgot to exit a context, emulate a final uninstall and reset.
    blocker._ACTIVE_CONFIGS.clear()  # noqa: SLF001


# ---------- BlockConfig.from_kwargs mapping ----------


def test_blockconfig_from_kwargs_aliases():
    cfg = BlockConfig.from_kwargs(
        no_network=True,
        no_subprocess=True,
        fs_readonly=True,
        fs_root="/tmp/sbx",
        block_native=True,
        allow_localhost=True,
        allow_domains=["a.example", "b.example"],
        trace=True,
    )
    assert cfg.block_network is True
    assert cfg.block_subprocess is True
    assert cfg.fs_readonly is True
    assert cfg.fs_root == "/tmp/sbx"
    assert cfg.block_native is True
    assert cfg.allow_localhost is True
    assert cfg.allow_domains == ["a.example", "b.example"]
    assert cfg.trace is True


def test_blockconfig_from_kwargs_unknown_key_rejected():
    with pytest.raises(TypeError):
        BlockConfig.from_kwargs(unknown_flag=True)  # type: ignore[arg-type]


# ---------- Context manager: install/uninstall semantics ----------


def test_hermetic_blocker_installs_with_expected_sections(reset_blocker_state):
    R = reset_blocker_state
    with hermetic_blocker(
        block_network=True,
        block_subprocess=False,
        fs_readonly=True,
        fs_root="/sandbox",
        block_native=True,
        allow_localhost=True,
        allow_domains=("ok.example",),
        trace=True,
    ):
        pass

    # Enter installs once, exit re-applies to empty by uninstalling once more.
    assert len(R.calls["install_all"]) == 1
    assert len(R.calls["uninstall_all"]) == 2

    args = R.calls["install_all"][0]
    # When enabled => dict with expected keys; else => None
    assert isinstance(args["net"], dict) and args["net"]["allow_localhost"] is True
    assert args["net"]["allow_domains"] == [
        "ok.example"
    ]  # tuple coerced to list at API boundary
    assert args["net"]["trace"] is True

    assert args["subproc"] is None  # disabled
    assert (
        isinstance(args["fs"], dict)
        and args["fs"]["fs_root"] == "/sandbox"
        and args["fs"]["trace"] is True
    )
    assert isinstance(args["imports"], dict) and args["imports"]["trace"] is True


def test_hermetic_blocker_calls_install_even_if_all_sections_disabled(
    reset_blocker_state,
):
    R = reset_blocker_state
    with hermetic_blocker():  # everything false/None
        pass
    assert len(R.calls["install_all"]) == 1  # still called with all None sections
    assert R.calls["install_all"][0] == dict(
        net=None, subproc=None, fs=None, env=None, code=None, interp=None, imports=None
    )
    assert len(R.calls["uninstall_all"]) == 2


def test_nested_contexts_reapply_merged_policy(reset_blocker_state):
    R = reset_blocker_state
    # nest: each policy change re-applies the merged guard set
    with hermetic_blocker(block_network=True):
        with hermetic_blocker(block_network=True, block_subprocess=True):
            with hermetic_blocker(fs_readonly=True):
                # still inside
                pass
        assert len(R.calls["uninstall_all"]) == 5
    assert len(R.calls["install_all"]) == 5
    assert len(R.calls["uninstall_all"]) == 6
    assert R.calls["install_all"][1]["subproc"]["trace"] is False
    assert R.calls["install_all"][2]["fs"]["trace"] is False


def test_nested_contexts_merge_policies(reset_blocker_state):
    R = reset_blocker_state
    with hermetic_blocker(block_network=True, allow_domains=["outer.example"]):
        with hermetic_blocker(block_subprocess=True, allow_domains=["inner.example"]):
            merged = R.calls["install_all"][-1]
            assert merged["net"]["allow_domains"] == [
                "outer.example",
                "inner.example",
            ]
            assert merged["subproc"] == {"trace": False}


def test_exception_not_suppressed_and_uninstalls(reset_blocker_state):
    R = reset_blocker_state

    class Boom(Exception): ...

    with pytest.raises(Boom):
        with hermetic_blocker(block_network=True):
            raise Boom("kaboom")
    # uninstall executed in finally
    assert len(R.calls["uninstall_all"]) == 2


# ---------- Decorator usage (ContextDecorator) ----------


def test_decorator_wraps_function_and_orders_install_uninstall(reset_blocker_state):
    R = reset_blocker_state
    timeline = R.calls["timeline"]

    @hermetic_blocker(block_network=True)
    def target():
        timeline.append("func")

    target()
    assert timeline == ["uninstall", "install", "func", "uninstall"]


def test_with_hermetic_alias_equivalent(reset_blocker_state):
    R = reset_blocker_state
    timeline = R.calls["timeline"]

    @with_hermetic(block_subprocess=True, trace=True)
    def target():
        timeline.append("func")

    target()
    assert timeline == ["uninstall", "install", "func", "uninstall"]
    args = R.calls["install_all"][0]
    assert isinstance(args["subproc"], dict) and args["subproc"]["trace"] is True


# ---------- Async context manager ----------


@pytest.mark.asyncio
async def test_async_with_context_manager(reset_blocker_state):
    R = reset_blocker_state
    async with hermetic_blocker(block_network=True, block_native=True):
        # inside: exactly one install
        assert len(R.calls["install_all"]) == 1
        # reapply starts with an uninstall
        assert len(R.calls["uninstall_all"]) == 1
    # after exit: a second uninstall clears the final policy
    assert len(R.calls["uninstall_all"]) == 2


# ---------- Parameter plumbing edge-cases ----------


def test_allow_domains_iterable_and_localhost_flag_plumbed(reset_blocker_state):
    R = reset_blocker_state
    allow = {"a.example", "b.example"}  # set iterable
    with hermetic_blocker(
        block_network=True, allow_localhost=True, allow_domains=allow
    ):
        pass
    args = R.calls["install_all"][0]["net"]
    assert args["allow_localhost"] is True
    # input set should have been realized to a list; order not guaranteed, so compare as sets
    assert set(args["allow_domains"]) == allow
