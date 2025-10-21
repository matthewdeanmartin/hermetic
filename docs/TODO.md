# TODO

## Execve
Support not using os.execve (not sure if it is fully windows compatible)


## resource module
Support this sort of subprocess

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