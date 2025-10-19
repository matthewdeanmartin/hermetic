# hermetic/bootstrap.py
from __future__ import annotations
import json
import os
import tempfile
from textwrap import dedent
from typing import Dict, Any
from .errors import BootstrapError

# Minimal bootstrap sitecustomize that installs guards without requiring hermetic package to be importable.
# Encodes guards inline to survive foreign interpreters/venvs.

_SITE_CUSTOMIZE = dedent(
    r'''
    import os, sys, json, socket, ssl, subprocess, asyncio, builtins, importlib.machinery as mach, pathlib, time
    
    class _HPolicy(RuntimeError): pass
    
    # policy-aware excepthook so bootstrap exits cleanly on guard violations
    _orig_excepthook = sys.excepthook
    def _hermetic_excepthook(exctype, value, tb):
        # Don’t intercept KeyboardInterrupt
        if exctype is KeyboardInterrupt:
            return _orig_excepthook(exctype, value, tb)
        # Our policy exceptions get a clean, consistent exit
        if exctype.__name__ in {"_HPolicy", "PolicyViolation"}:
            try:
                sys.stderr.write(f"hermetic: blocked action: {value}\n")
                sys.stderr.flush()
                time.sleep(1)
            finally:
                os._exit(2)  # hard-exit: no teardown that might deadlock
        # otherwise, default behavior
        return _orig_excepthook(exctype, value, tb)
    
    sys.excepthook = _hermetic_excepthook
    
    cfg = json.loads(os.environ.pop("HERMETIC_FLAGS_JSON", "{}"))
    trace = bool(cfg.get("trace"))
    def _tr(msg): 
        if trace: 
            print(f"[hermetic] {msg}", file=sys.stderr, flush=True)

    # --- network ---
    if cfg.get("no_network"):
        _orig = {"socket": socket.socket, "create": socket.create_connection, "dns": socket.getaddrinfo, "wrap": ssl.SSLContext.wrap_socket}
        ALLOW_LOCAL = bool(cfg.get("allow_localhost"))
        ALLOW_DOMAINS = set([d.lower() for d in cfg.get("allow_domains", []) if d])
        META = {"169.254.169.254", "metadata.google.internal"}
        LOCAL = {"127.0.0.1","::1","localhost","0.0.0.0"}
        def _allowed(host:str)->bool:
            h = (host or "").lower()
            if h in META: return False
            if ALLOW_LOCAL and h in LOCAL: return True
            return any((d in h) for d in ALLOW_DOMAINS)
        def _guard_socket(*a,**k):
            _tr("blocked socket.socket reason=no-network"); raise _HPolicy("network disabled")
        def _guard_create(addr,*a,**k):
            host = addr[0] if isinstance(addr,(tuple,list)) else str(addr)
            if _allowed(host): return _orig["create"](addr,*a,**k)
            _tr(f"blocked socket.create_connection host={host} reason=no-network"); raise _HPolicy("network disabled")
        def _guard_dns(host,*a,**k):
            if _allowed(str(host)): return _orig["dns"](host,*a,**k)
            _tr(f"blocked socket.getaddrinfo host={host} reason=no-network"); raise _HPolicy("network disabled")
        def _guard_wrap(self,sock,*a,**k):
            _tr("blocked ssl.wrap_socket reason=no-network"); raise _HPolicy("network disabled")
        socket.socket = _guard_socket
        socket.create_connection = _guard_create
        socket.getaddrinfo = _guard_dns
        ssl.SSLContext.wrap_socket = _guard_wrap

    # --- subprocess ---
    if cfg.get("no_subprocess"):
        def _deny(*a,**k): _tr("blocked subprocess reason=no-subprocess"); raise _HPolicy("subprocess disabled")
        subprocess.Popen = _deny
        subprocess.run = _deny
        subprocess.call = _deny
        subprocess.check_output = _deny
        os.system = _deny
        asyncio.create_subprocess_exec = _deny
        asyncio.create_subprocess_shell = _deny

    # --- fs readonly ---
    if cfg.get("fs_readonly"):
        ROOT = cfg.get("fs_root")
        _o = {"open": builtins.open, "Popen": pathlib.Path.open, "os.open": os.open}
        def _norm(p): 
            try: import os as _os; return _os.path.realpath(p)
            except Exception: return p
        def _within(p, r): 
            P, R = _norm(p), _norm(r)
            return P==R or P.startswith(R + ("/" if "/" in R else "\\"))
        def _open_guard(f, mode="r", *a, **k):
            path = str(f)
            if any(m in mode for m in ("w","a","x","+")): _tr(f"blocked open write path={path}"); raise _HPolicy("fs readonly")
            if ROOT and not _within(path, ROOT): _tr(f"blocked open read-outside-root path={path}"); raise _HPolicy("read outside root")
            return _o["open"](f, mode, *a, **k)
        builtins.open = _open_guard
        pathlib.Path.open = lambda self,*a,**k: _open_guard(str(self), *a, **k)
        os.open = lambda path, flags, *a, **k: _open_guard(path, "r" if flags & getattr(os,"O_RDONLY",0) else "w")
        def _deny(*a,**k): _tr("blocked fs mutation"); raise _HPolicy("fs mutation disabled")
        for name in ("remove","rename","replace","unlink","rmdir","mkdir","makedirs"):
            setattr(__import__("os"), name, _deny)

    # --- strict imports ---
    if cfg.get("strict_imports"):
        _origExt = mach.ExtensionFileLoader
        _origImp = builtins.__import__
        def _trimp(n): _tr(f"blocked import name={n}")
        class GuardedExtLoader(_origExt):
            def create_module(self, spec): _tr(f"blocked native import spec={spec.name}"); raise _HPolicy("native import blocked")
        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".",1)[0]
            if root in {"ctypes","cffi"}: _trimp(name); raise _HPolicy("import blocked")
            return _origImp(name, globals, locals, fromlist, level)
        mach.ExtensionFileLoader = GuardedExtLoader
        builtins.__import__ = guarded_import
    '''
)

def write_sitecustomize(flags: Dict[str, Any]) -> str:
    try:
        d = tempfile.mkdtemp(prefix="hermetic_site_")
        path = os.path.join(d, "sitecustomize.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_SITE_CUSTOMIZE)
        os.environ["HERMETIC_FLAGS_JSON"] = json.dumps(flags)
        return d
    except Exception as e:
        raise BootstrapError(f"failed to write sitecustomize: {e}")
