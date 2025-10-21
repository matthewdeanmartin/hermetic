# hermetic

Run a python tool, or your application with certain APIs disabled, such as network or subprocess.

The previously safe library you depend on was highjacked and will be sending your password files to a remote server.
Or you installed this and the malicious hackers didn't include evasive code to defeat this fig leaf of a security
feature and the day is saved.

If Alice and Bob know about your application and specifically are targeting this, this tool won't help.

## Usage

### Command-Line Interface

Use the `hermetic` command to run any Python console script, separating its arguments with `--`.

**Syntax**: `hermetic [flags] -- <command> [command_args]`

#### Common Flags:

  - `--no-network`: Disable all network activity.
  - `--allow-localhost`: Allows network connections to localhost (used with `--no-network`).
  - `--allow-domain <domain>`: Allows connections to a specific domain (repeatable).
  - `--no-subprocess`: Disable creating new processes.
  - `--fs-readonly[=/path/to/root]`: Make the filesystem read-only. Optionally, restrict all reads to be within the specified root directory.
  - `--block-native`: Block imports of native C extensions.
  - `--profile <name>`: Apply a pre-configured profile (e.g., `block-all`).
  - `--trace`: Print a message to stderr when an action is blocked.

#### CLI Examples:

**Block network access for the `httpie` tool:**

```bash
$ hermetic --no-network -- http [https://example.com](https://example.com)

hermetic: blocked action: network disabled: DNS(example.com)
```

**Run a script in a read-only filesystem where it can only read from `./sandbox`:**

```bash
$ hermetic --fs-readonly=./sandbox -- python my_script.py

# my_script.py will raise PolicyViolation if it tries to read outside ./sandbox
# or write anywhere.
```

**Apply the `block-all` profile to completely lock down a script:**

```bash
$ hermetic --profile block-all -- my_analyzer.py --input data.csv
```

-----

### Programmatic API

You can use `hermetic` directly in your Python code via the `hermetic_blocker` context manager or the `@with_hermetic` decorator.

#### Decorator

The `@with_hermetic` decorator is the easiest way to apply guards to an entire function.

```python
from hermetic import with_hermetic
import requests

@with_hermetic(block_network=True, allow_domains=["api.internal.com"])
def process_data():
    # This will fail because all network access is blocked by default.
    # requests.get("https://example.com") # --> raises PolicyViolation

    # This is allowed because the domain is on the allow-list.
    return requests.get("https://api.internal.com/data")

process_data()
```

#### Context Manager

For more granular control, use the `hermetic_blocker` context manager.

```python
from hermetic import hermetic_blocker
import os

def check_system():
    # Subprocesses are allowed here
    os.system("echo 'Checking system...'")

    with hermetic_blocker(block_subprocess=True):
        # Inside this block, os.system() would raise a PolicyViolation
        print("Running in a sandboxed context.")
        os.system("echo 'This will fail.'") # --> raises PolicyViolation

    # Subprocesses are allowed again
    os.system("echo 'Exited sandbox.'")

check_system()
```

## Where could this work?

There are APIs you don't need but an application or 3rd party library you depend on needs. So you block them.

The 3rd party library must be unaware of hermetic or monkeypatching. Import order is important, hermetic must run
early enough to intercept all imports to the banned API. Then use of the banned API is blocked and the whole app stops.

This already works in unit testing where there isn't an adversarial relationship between the developers testing the code
and writing the code under test, where you block network traffic to guarantee a unit test is pure of network side
effects.

## Is this defeatable?

Yes, by many routes. Native code, import order tricks, undoing a monkey patch, bringing along a vendorized copy of APIs,
and so on.

This is "envelope instead of postcard" level security. This is "lock your door with standard key that can be picked with
a $5 purchase on Ebay" level security.

Real sandboxing is running your code in a docker container.

## Prior Art

This technique of monkey-patching for isolation is well-established, particularly in the testing ecosystem.

  - [pytest-socket](https://pypi.org/project/pytest-socket/): Disables sockets during tests.
  - [pytest-network](https://pypi.org/project/pytest-network/): Disables networking during tests.

For stronger sandboxing, consider:

  - [pysandbox](https://github.com/vstinner/pysandbox): Uses Linux `seccomp` for kernel-level syscall filtering.
  - [RestrictedPython](https://pypi.org/project/RestrictedPython/): Rewrites Python AST to enforce constraints.
  - [Docker](https://www.docker.com/): OS-level virtualization.
