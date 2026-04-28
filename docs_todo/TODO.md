# TODO

## New rules

If you block network, subprocess, you have to also block native code interop libraries otherwise it is trivial to
accomplish the same with C interop.

If you blacklist subprocess, you may also need to blacklist the subprocess replacement libraries, e.g. `sh`

If you start blacklisting, then you may need to whitelist or you can't blacklist libraries you don't know about.

## Execve

Support not using os.execve (not sure if it is fully windows compatible)

## resource module

This is a unix only feature as a defense against parasitic/excessive cpu usage

https://docs.python.org/3/library/resource.html

```
import subprocess
import resource

def limit_resources():
    # Limit CPU time, memory, etc.
    resource.setrlimit(resource.RLIMIT_CPU, (1, 1))

subprocess.run(
    ['python', '-c', untrusted_code],
    preexec_fn=limit_resources,
    timeout=5,
    env={'PATH': '/usr/bin'}  # minimal environment
)
```