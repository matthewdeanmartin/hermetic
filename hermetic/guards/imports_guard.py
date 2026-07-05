# hermetic/guards/imports_guard.py
"""Guards that block native extensions and denied imports."""

from __future__ import annotations

import builtins
import _imp
import importlib
import importlib.machinery as mach
import importlib.util
import sys
import zipimport
from textwrap import dedent
from typing import Any, Iterable

from hermetic.errors import PolicyViolation

_installed = False
_originals: dict[str, Any] = {}

# Names whose top-level package import is blocked when block_native is on.
# We block the FFI surface plus ctypes' private siblings — without these,
# attackers can re-create CDLL/PyDLL/etc.
_DENY_NAMES = {
    "ctypes",
    "_ctypes",
    "cffi",
    "_cffi_backend",
}

# Subprocess-replacement libraries: these wrap subprocess.Popen and friends,
# but many of them capture references at import time, so blocking the import
# is more reliable than patching them after the fact. Only enabled when the
# subprocess guard is also requested.
_SUBPROC_REPLACEMENT_NAMES = {
    "sh",
    "pexpect",
    "plumbum",
    "sarge",
    "delegator",
}

# Serialization modules whose load-side (`pickle.loads`, `marshal.loads`,
# `shelve.open(...)['k']`) invokes arbitrary callables named by the byte
# stream. We can't realistically patch every reachable callable, so when the
# caller has opted out of dynamic code execution we refuse the imports
# wholesale. Plugins that legitimately need serialization can use JSON,
# configparser, msgpack-without-ext, etc.
_PICKLE_NAMES = {
    "pickle",
    "_pickle",
    "cPickle",  # py2-era alias; harmless to list, free coverage if a venv has it
    "marshal",
    "shelve",
    "dill",
    "cloudpickle",
    "jsonpickle",
}

_CTYPES_ATTRS = ("CDLL", "PyDLL", "WinDLL", "OleDLL", "LibraryLoader")
_CTYPES_LOADER_ATTRS = ("cdll", "pydll", "windll", "oledll")
_CTYPES_UTIL_ATTRS = ("find_library", "find_msvcrt")
_CFFI_ATTRS = ("FFI", "dlopen", "verify")


def _deny_use(name: str) -> Any:
    """Raise a policy violation for direct native interface use."""
    raise PolicyViolation(
        f"native interface blocked: {name}", guard="imports", target=name
    )


class _NativeExtensionFinder:
    """Meta path finder that rejects native extension specs."""

    def __init__(self, *, ext_loader_type: type[Any], trace_func: Any) -> None:
        """Remember the loader type that identifies native extensions."""
        self._ext_loader_type = ext_loader_type
        self._trace = trace_func

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        """Reject import specs that resolve to native extension loaders."""
        spec = mach.PathFinder.find_spec(fullname, path, target)
        if spec and isinstance(spec.loader, self._ext_loader_type):
            self._trace(f"blocked native import spec={fullname}")
            raise PolicyViolation(
                f"native import blocked: {fullname}", guard="imports", target=fullname
            )
        return spec


def _patch_module_attrs(mod_name: str, attrs: tuple[str, ...]) -> None:
    """Replace selected module attributes with policy-raising stand-ins."""
    mod = sys.modules.get(mod_name)
    if mod is None:
        return
    for attr in attrs:
        if hasattr(mod, attr):
            key = f"module_attr:{mod_name}:{attr}"
            if key not in _originals:
                _originals[key] = getattr(mod, attr)
            try:
                setattr(
                    mod,
                    attr,
                    lambda *a, _name=f"{mod_name}.{attr}", **k: _deny_use(_name),
                )
            except (AttributeError, TypeError):
                # Some C-level attributes are read-only; skip them.
                pass


def _patch_loaded_native_modules() -> None:
    """Patch already-imported native helper modules in place."""
    _patch_module_attrs("ctypes", _CTYPES_ATTRS + _CTYPES_LOADER_ATTRS)
    _patch_module_attrs("ctypes.util", _CTYPES_UTIL_ATTRS)
    _patch_module_attrs("cffi", _CFFI_ATTRS)


def _invalidate_finder_caches() -> None:
    """Refresh importlib caches after changing import guard state."""
    try:
        importlib.invalidate_caches()
    except Exception:  # nosec: B110:try_except_pass
        pass


def _normalize_deny_names(names: Iterable[str]) -> set[str]:
    """Trim and filter the configured denied import names."""
    return {name.strip() for name in names if name and name.strip()}


def _matches_denied_import(name: str, denied_name: str) -> bool:
    """Check whether an import matches a denied module prefix."""
    root = name.split(".", 1)[0]
    return (
        name == denied_name or name.startswith(f"{denied_name}.") or root == denied_name
    )


def _absolute_import_names(
    name: str,
    globals_dict: Any = None,
    fromlist: Any = (),
    level: int = 0,
) -> set[str]:
    """Return the absolute module names an import request may load."""
    package = ""
    if globals_dict:
        package = str(
            globals_dict.get("__package__")
            or globals_dict.get("__name__")
            or ""
        )
    if level:
        try:
            absolute = importlib.util.resolve_name(f"{'.' * level}{name}", package)
        except (ImportError, ValueError):
            absolute = name
    else:
        absolute = name

    names = {absolute} if absolute else set()
    if absolute and fromlist:
        for item in fromlist:
            if isinstance(item, str) and item and item != "*":
                names.add(f"{absolute}.{item}")
    return names


def _loader_module_name(loader: Any, module: Any = None) -> str:
    """Extract the best available module name from a loader invocation."""
    spec = getattr(module, "__spec__", None)
    return str(
        getattr(spec, "name", "")
        or getattr(module, "__name__", "")
        or getattr(loader, "name", "")
    )


def install(
    *,
    block_native: bool = True,
    trace: bool = False,
    block_subprocess_libs: bool = False,
    block_pickle: bool = False,
    deny_imports: Iterable[str] = (),
) -> None:
    """Patch import machinery to reject configured modules and FFI surfaces."""
    global _installed
    if _installed:
        return
    _installed = True
    _originals["__import__"] = builtins.__import__
    _originals["importlib.import_module"] = importlib.import_module
    _originals["PathFinder.find_spec"] = mach.PathFinder.__dict__["find_spec"]
    _originals["PathFinder.find_spec_bound"] = mach.PathFinder.find_spec
    _originals["SourceFileLoader.exec_module"] = mach.SourceFileLoader.exec_module
    _originals["SourcelessFileLoader.exec_module"] = (
        mach.SourcelessFileLoader.exec_module
    )
    _originals["zipimporter.exec_module"] = zipimport.zipimporter.exec_module
    if block_native:
        _originals["ExtLoader"] = mach.ExtensionFileLoader
        _originals["ExtensionFileLoader.create_module"] = (
            mach.ExtensionFileLoader.create_module
        )
        _originals["ExtensionFileLoader.exec_module"] = (
            mach.ExtensionFileLoader.exec_module
        )
        _originals["_imp.create_dynamic"] = _imp.create_dynamic
        _originals["_imp.exec_dynamic"] = _imp.exec_dynamic
        _originals["sys.meta_path"] = sys.meta_path

    deny_names = _normalize_deny_names(deny_imports)
    if block_native:
        deny_names |= _DENY_NAMES
    if block_native and block_subprocess_libs:
        deny_names |= _SUBPROC_REPLACEMENT_NAMES
    if block_pickle:
        deny_names |= _PICKLE_NAMES

    def _trace(msg: str) -> None:
        """Emit a trace message when an import is blocked."""
        if trace:
            print(f"[hermetic] {msg}", file=sys.stderr, flush=True)

    def _check_names(names: Iterable[str]) -> None:
        """Raise when any candidate absolute name is denied."""
        for candidate in names:
            if any(
                _matches_denied_import(candidate, denied_name)
                for denied_name in deny_names
            ):
                _trace(f"blocked import name={candidate}")
                raise PolicyViolation(
                    f"import blocked: {candidate}",
                    guard="imports",
                    target=candidate,
                )

    def _guard_pathfinder_find_spec(
        cls: type[Any],
        fullname: str,
        path: Any = None,
        target: Any = None,
    ) -> Any:
        """Enforce name and native policy for direct PathFinder use."""
        del cls
        _check_names((fullname,))
        spec = _originals["PathFinder.find_spec_bound"](fullname, path, target)
        if (
            block_native
            and spec
            and isinstance(spec.loader, _originals["ExtLoader"])
        ):
            _trace(f"blocked native import spec={fullname}")
            raise PolicyViolation(
                f"native import blocked: {fullname}",
                guard="imports",
                target=fullname,
            )
        return spec

    def _guard_source_exec(loader: Any, module: Any) -> Any:
        """Reject denied modules executed through a direct source loader."""
        _check_names((_loader_module_name(loader, module),))
        return _originals["SourceFileLoader.exec_module"](loader, module)

    def _guard_sourceless_exec(loader: Any, module: Any) -> Any:
        """Reject denied modules executed through a direct bytecode loader."""
        _check_names((_loader_module_name(loader, module),))
        return _originals["SourcelessFileLoader.exec_module"](loader, module)

    def _guard_zip_exec(loader: Any, module: Any) -> Any:
        """Reject denied modules executed through a direct zip loader."""
        _check_names((_loader_module_name(loader, module),))
        return _originals["zipimporter.exec_module"](loader, module)

    if block_native:
        native_finder = _NativeExtensionFinder(
            ext_loader_type=_originals["ExtLoader"],
            trace_func=_trace,
        )
        sys.meta_path = [native_finder, *list(sys.meta_path)]

        class GuardedExtLoader(mach.ExtensionFileLoader):
            """Loader stub that refuses to create native extension modules."""

            def create_module(self, spec: Any) -> Any:
                """Reject native module creation during import loading."""
                _trace(f"blocked native import spec={spec.name}")
                raise PolicyViolation(
                    f"native import blocked: {spec.name}",
                    guard="imports",
                    target=spec.name,
                )

            def exec_module(self, module: Any) -> Any:
                """Reject native module execution through a direct loader."""
                name = _loader_module_name(self, module)
                _trace(f"blocked native import spec={name}")
                raise PolicyViolation(
                    f"native import blocked: {name}",
                    guard="imports",
                    target=name,
                )

        def _deny_dynamic(spec_or_module: Any, *args: Any, **kwargs: Any) -> Any:
            """Reject direct use of CPython's native-module loader hooks."""
            del args, kwargs
            name = str(
                getattr(spec_or_module, "name", "")
                or getattr(spec_or_module, "__name__", "")
            )
            _trace(f"blocked native import spec={name}")
            raise PolicyViolation(
                f"native import blocked: {name}",
                guard="imports",
                target=name,
            )

    def guarded_import(
        name: str,
        globals: Any = None,  # pylint: disable=redefined-builtin
        locals: Any = None,  # pylint: disable=redefined-builtin
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        """Reject denied imports before delegating to Python's importer."""
        _check_names(_absolute_import_names(name, globals, fromlist, level))
        return _originals["__import__"](name, globals, locals, fromlist, level)

    def guarded_import_module(name: str, package: str | None = None) -> Any:
        """Reject denied imports through ``importlib.import_module``."""
        absolute = (
            importlib.util.resolve_name(name, package) if name.startswith(".") else name
        )
        _check_names((absolute,))
        return _originals["importlib.import_module"](name, package)

    mach.PathFinder.find_spec = classmethod(_guard_pathfinder_find_spec)  # type: ignore[method-assign,assignment]
    mach.SourceFileLoader.exec_module = _guard_source_exec  # type: ignore[method-assign,assignment]
    mach.SourcelessFileLoader.exec_module = _guard_sourceless_exec  # type: ignore[method-assign,assignment]
    zipimport.zipimporter.exec_module = _guard_zip_exec  # type: ignore[method-assign,assignment]
    if block_native:
        mach.ExtensionFileLoader = GuardedExtLoader  # type: ignore[misc]
        _originals["ExtLoader"].create_module = GuardedExtLoader.create_module
        _originals["ExtLoader"].exec_module = GuardedExtLoader.exec_module
        _imp.create_dynamic = _deny_dynamic
        _imp.exec_dynamic = _deny_dynamic
    builtins.__import__ = guarded_import
    importlib.import_module = guarded_import_module
    if block_native:
        _patch_loaded_native_modules()
        _invalidate_finder_caches()


def uninstall() -> None:
    """Restore the original import machinery and patched attributes."""
    global _installed
    if not _installed:
        return
    mach.PathFinder.find_spec = _originals.pop("PathFinder.find_spec")  # type: ignore[method-assign]
    mach.SourceFileLoader.exec_module = _originals.pop("SourceFileLoader.exec_module")  # type: ignore[method-assign]
    mach.SourcelessFileLoader.exec_module = _originals.pop(  # type: ignore[method-assign]
        "SourcelessFileLoader.exec_module"
    )
    zipimport.zipimporter.exec_module = _originals.pop("zipimporter.exec_module")  # type: ignore[method-assign]
    _originals.pop("PathFinder.find_spec_bound", None)
    importlib.import_module = _originals.pop("importlib.import_module")
    if "ExtLoader" in _originals:
        original_ext_loader = _originals.pop("ExtLoader")
        original_ext_loader.create_module = _originals.pop(
            "ExtensionFileLoader.create_module"
        )
        original_ext_loader.exec_module = _originals.pop(
            "ExtensionFileLoader.exec_module"
        )
        mach.ExtensionFileLoader = original_ext_loader  # type: ignore[misc]
        _imp.create_dynamic = _originals.pop("_imp.create_dynamic")
        _imp.exec_dynamic = _originals.pop("_imp.exec_dynamic")
    builtins.__import__ = _originals.pop("__import__")
    if "sys.meta_path" in _originals:
        sys.meta_path = _originals.pop("sys.meta_path")
    for key in [item for item in _originals if item.startswith("module_attr:")]:
        _, mod_name, attr = key.split(":", 2)
        mod = sys.modules.get(mod_name)
        if mod is not None:
            try:
                setattr(mod, attr, _originals.pop(key))
            except (AttributeError, TypeError):
                _originals.pop(key, None)
        else:
            _originals.pop(key, None)
    _invalidate_finder_caches()
    _installed = False


# --- Code for bootstrap.py generation ---
BOOTSTRAP_CODE = dedent(
    r"""
# --- strict imports ---
if cfg.get("block_native") or cfg.get("deny_imports") or cfg.get("no_code_exec"):
    _origExt = mach.ExtensionFileLoader
    _origImp = builtins.__import__
    _origImportModule = importlib.import_module
    _origMetaPath = sys.meta_path
    _origPathFindSpec = mach.PathFinder.find_spec
    _origSourceExec = mach.SourceFileLoader.exec_module
    _origSourcelessExec = mach.SourcelessFileLoader.exec_module
    _origZipExec = zipimport.zipimporter.exec_module
    _origExtCreate = _origExt.create_module
    _origExtExec = _origExt.exec_module
    _origCreateDynamic = _imp.create_dynamic
    _origExecDynamic = _imp.exec_dynamic
    _BLOCK_NATIVE = bool(cfg.get("block_native"))
    _BLOCK_SUBPROC_LIBS = bool(cfg.get("no_subprocess"))
    _BLOCK_PICKLE = bool(cfg.get("no_code_exec"))
    _DENY = set([n.strip() for n in cfg.get("deny_imports", []) if n and n.strip()])
    if _BLOCK_NATIVE:
        _DENY |= {"ctypes","_ctypes","cffi","_cffi_backend"}
    if _BLOCK_NATIVE and _BLOCK_SUBPROC_LIBS:
        _DENY |= {"sh","pexpect","plumbum","sarge","delegator"}
    if _BLOCK_PICKLE:
        _DENY |= {"pickle","_pickle","cPickle","marshal","shelve","dill","cloudpickle","jsonpickle"}
    def _deny_native_use(name): raise _HPolicy(f"native interface blocked: {name}")
    def _match_import(name, denied):
        root = name.split(".", 1)[0]
        return name == denied or name.startswith(denied + ".") or root == denied
    def _absolute_import_names(name, globals_dict=None, fromlist=(), level=0):
        package = ""
        if globals_dict:
            package = str(globals_dict.get("__package__") or globals_dict.get("__name__") or "")
        if level:
            try: absolute = importlib.util.resolve_name("." * level + name, package)
            except (ImportError, ValueError): absolute = name
        else:
            absolute = name
        names = {absolute} if absolute else set()
        if absolute and fromlist:
            for item in fromlist:
                if isinstance(item, str) and item and item != "*":
                    names.add(absolute + "." + item)
        return names
    def _check_names(names):
        for candidate in names:
            if any(_match_import(candidate, denied) for denied in _DENY):
                _tr(f"blocked import name={candidate}")
                raise _HPolicy(f"import blocked: {candidate}")
    def _loader_name(loader, module=None):
        spec = getattr(module, "__spec__", None)
        return str(getattr(spec, "name", "") or getattr(module, "__name__", "") or getattr(loader, "name", ""))
    def _patch_attrs(mod_name, attrs):
        m = sys.modules.get(mod_name)
        if m is None: return
        for a in attrs:
            if hasattr(m, a):
                try: setattr(m, a, lambda *_a, _n=f"{mod_name}.{a}", **_k: _deny_native_use(_n))
                except (AttributeError, TypeError): pass
    def _patch_loaded_native_modules():
        _patch_attrs("ctypes", ("CDLL","PyDLL","WinDLL","OleDLL","LibraryLoader","cdll","pydll","windll","oledll"))
        _patch_attrs("ctypes.util", ("find_library","find_msvcrt"))
        _patch_attrs("cffi", ("FFI","dlopen","verify"))
    class _NativeExtensionFinder:
        def __init__(self, ext_loader_type):
            self._ext_loader_type = ext_loader_type
        def find_spec(self, fullname, path=None, target=None):
            _check_names((fullname,))
            spec = _origPathFindSpec(fullname, path, target)
            if spec and isinstance(spec.loader, self._ext_loader_type):
                _tr(f"blocked native import spec={fullname}")
                raise _HPolicy(f"native import blocked: {fullname}")
            return spec
    class GuardedExtLoader(_origExt):
        def create_module(self, spec): _tr(f"blocked native import spec={spec.name}"); raise _HPolicy("native import blocked")
        def exec_module(self, module):
            name = _loader_name(self, module)
            _tr(f"blocked native import spec={name}")
            raise _HPolicy(f"native import blocked: {name}")
    def _guard_path_find_spec(cls, fullname, path=None, target=None):
        _check_names((fullname,))
        spec = _origPathFindSpec(fullname, path, target)
        if _BLOCK_NATIVE and spec and isinstance(spec.loader, _origExt):
            _tr(f"blocked native import spec={fullname}")
            raise _HPolicy(f"native import blocked: {fullname}")
        return spec
    def _guard_source_exec(loader, module):
        _check_names((_loader_name(loader, module),))
        return _origSourceExec(loader, module)
    def _guard_sourceless_exec(loader, module):
        _check_names((_loader_name(loader, module),))
        return _origSourcelessExec(loader, module)
    def _guard_zip_exec(loader, module):
        _check_names((_loader_name(loader, module),))
        return _origZipExec(loader, module)
    def _deny_dynamic(spec_or_module, *args, **kwargs):
        name = str(getattr(spec_or_module, "name", "") or getattr(spec_or_module, "__name__", ""))
        _tr(f"blocked native import spec={name}")
        raise _HPolicy(f"native import blocked: {name}")
    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        _check_names(_absolute_import_names(name, globals, fromlist, level))
        return _origImp(name, globals, locals, fromlist, level)
    def guarded_import_module(name, package=None):
        absolute = importlib.util.resolve_name(name, package) if name.startswith(".") else name
        _check_names((absolute,))
        return _origImportModule(name, package)
    mach.PathFinder.find_spec = classmethod(_guard_path_find_spec)
    mach.SourceFileLoader.exec_module = _guard_source_exec
    mach.SourcelessFileLoader.exec_module = _guard_sourceless_exec
    zipimport.zipimporter.exec_module = _guard_zip_exec
    if _BLOCK_NATIVE:
        sys.meta_path = [_NativeExtensionFinder(_origExt)] + list(_origMetaPath)
        mach.ExtensionFileLoader = GuardedExtLoader
        _origExt.create_module = GuardedExtLoader.create_module
        _origExt.exec_module = GuardedExtLoader.exec_module
        _imp.create_dynamic = _deny_dynamic
        _imp.exec_dynamic = _deny_dynamic
    builtins.__import__ = guarded_import
    importlib.import_module = guarded_import_module
    if _BLOCK_NATIVE:
        _patch_loaded_native_modules()
        try:
            import importlib as _il; _il.invalidate_caches()
        except Exception: pass
"""
)
