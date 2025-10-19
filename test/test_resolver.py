# tests/test_resolver.py
import pytest
import os
import sys
from hermetic.resolver import resolve, TargetSpec

def test_resolve_module_attr():
    spec = resolve("module:attr")
    assert spec == TargetSpec(module="module", attr="attr", mode="inprocess")

# def test_resolve_script(tmp_path):
#     script = tmp_path / "script.py"
#     script.write_text("#!/usr/bin/env python\nprint('hello')")
#     spec = resolve(str(script))
#     assert spec.module == ""
#     assert spec.attr == "__main__"
#     assert spec.mode == "bootstrap"
#     assert spec.exe_path == str(script)

def test_resolve_module_fallback():
    spec = resolve("mymodule")
    assert spec == TargetSpec(module="mymodule", attr="__main__", mode="inprocess")