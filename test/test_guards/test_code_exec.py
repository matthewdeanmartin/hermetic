import importlib
import runpy
import sys

import pytest

from hermetic.errors import PolicyViolation
from hermetic.guards.code_exec import install, uninstall


def test_code_exec_guard_blocks_dynamic_execution(tmp_path):
    module_dir = tmp_path / "moddir"
    module_dir.mkdir()
    (module_dir / "guarded_mod.py").write_text("VALUE = 7\n", encoding="utf-8")
    sys.path.insert(0, str(module_dir))
    try:
        install(trace=True)
        try:
            with pytest.raises(PolicyViolation, match="eval"):
                eval("1 + 1")

            with pytest.raises(PolicyViolation, match="exec"):
                exec("x = 1", {})

            with pytest.raises(PolicyViolation, match="compile"):
                compile("1 + 1", "<string>", "eval")

            with pytest.raises(PolicyViolation, match="run_path"):
                runpy.run_path(str(module_dir / "guarded_mod.py"))

            mod = importlib.import_module("guarded_mod")
            assert mod.VALUE == 7
        finally:
            uninstall()
    finally:
        sys.modules.pop("guarded_mod", None)
        sys.path.remove(str(module_dir))
