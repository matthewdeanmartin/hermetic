# hermetic

[![PyPI version](https://badge.fury.io/py/hermetic.svg)](https://badge.fury.io/py/hermetic)

A lightweight, user-space sandbox for Python applications. `hermetic` lets you run Python code while disabling potentially dangerous capabilities like network access, subprocess execution, filesystem writes, and native C extensions.

It works by patching Python's standard library at runtime, making it a weak tool for reducing the attack surface of your application or third-party tools.

The previously safe library you depend on was highjacked and will be sending your password files to a remote server.
Or you installed this and the malicious hackers didn't include evasive code to defeat this fig leaf of a security
feature and the day is saved.

---

## Key Features

-   **Network Guard**: Block all outbound network connections and DNS lookups, with optional allow-lists for localhost or specific domains.
-   **Subprocess Guard**: Disable functions that create new processes, such as `subprocess.Popen` and `os.system`.
-   **Read-Only Filesystem**: Prevent all file writes, creations, and deletions. You can optionally restrict file reads to a specific directory tree.
-   **Native Code Guard**: Block the import of native C extensions (`.so`, `.pyd` files) and FFI libraries like `ctypes`.
-   **Flexible Integration**: Use it from the command line to wrap any Python script or as a decorator/context manager within your own code.
-   **Bootstrap Mode**: Can sandbox scripts that use a different Python interpreter than `hermetic` itself.

---

## Use Cases

### 1. Securing Your Application from Supply Chain Attacks

Your application relies on third-party dependencies. What happens if one of them is compromised in a new release? A malicious update could try to exfiltrate data from your environment.

By wrapping sensitive parts of your code with `hermetic`, you can enforce a "principle of least privilege." For example, a code linting function has no reason to access the network. By blocking network access, you can mitigate the risk of a compromised dependency sending your source code to an attacker.

**Example: Running a code formatter.**
```python
from hermetic import with_hermetic
import black

# This function can format code, but CANNOT access the network or filesystem.
@with_hermetic(block_network=True, fs_readonly=True)
def format_untrusted_code(code: str) -> str:
    try:
        # If a compromised version of `black` tried to make a network
        # call here, hermetic would raise a PolicyViolation.
        return black.format_str(code, mode=black.FileMode())
    except Exception as e:
        # Handle formatting errors
        return f"Error formatting code: {e}"

# Safely format code from an untrusted source.
formatted = format_untrusted_code("import os; os.system('ls')")




















Of course. Here is a revised `README.md` that covers the project's use cases, risks, and provides clear examples for both CLI and programmatic usage.

````markdown
# hermetic

[![PyPI version](https://badge.fury.io/py/hermetic.svg)](https://badge.fury.io/py/hermetic)

A lightweight, user-space sandbox for Python applications. `hermetic` lets you run Python code while disabling potentially dangerous capabilities like network access, subprocess execution, filesystem writes, and native C extensions.

It works by patching Python's standard library at runtime, making it a powerful tool for reducing the attack surface of your application or third-party tools.

---

## Key Features

-   **Network Guard**: Block all outbound network connections and DNS lookups, with optional allow-lists for localhost or specific domains.
-   **Subprocess Guard**: Disable functions that create new processes, such as `subprocess.Popen` and `os.system`.
-   **Read-Only Filesystem**: Prevent all file writes, creations, and deletions. You can optionally restrict file reads to a specific directory tree.
-   **Native Code Guard**: Block the import of native C extensions (`.so`, `.pyd` files) and FFI libraries like `ctypes`.
-   **Flexible Integration**: Use it from the command line to wrap any Python script or as a decorator/context manager within your own code.
-   **Bootstrap Mode**: Can sandbox scripts that use a different Python interpreter than `hermetic` itself.

---

## Use Cases

### 1. Securing Your Application from Supply Chain Attacks

Your application relies on third-party dependencies. What happens if one of them is compromised in a new release? A malicious update could try to exfiltrate data from your environment.

By wrapping sensitive parts of your code with `hermetic`, you can enforce a "principle of least privilege." For example, a code linting function has no reason to access the network. By blocking network access, you can mitigate the risk of a compromised dependency sending your source code to an attacker.

**Example: Running a code formatter.**
```python
from hermetic import with_hermetic
import black

# This function can format code, but CANNOT access the network or filesystem.
@with_hermetic(block_network=True, fs_readonly=True)
def format_untrusted_code(code: str) -> str:
    try:
        # If a compromised version of `black` tried to make a network
        # call here, hermetic would raise a PolicyViolation.
        return black.format_str(code, mode=black.FileMode())
    except Exception as e:
        # Handle formatting errors
        return f"Error formatting code: {e}"

# Safely format code from an untrusted source.
formatted = format_untrusted_code("import os; os.system('ls')")
````

### 2\. Lightweight Sandboxing of Third-Party CLI Tools

You might need to run a Python-based utility that you don't fully trust or simply want to ensure behaves as expected. `hermetic` allows you to run these tools with strict guardrails from your terminal. This is useful for running linters, documentation generators, or any tool that shouldn't have side effects.

**Example: Installing packages without network access (e.g., from a local cache).**

```bash
# This pip command will fail if it tries to access the network.
hermetic --no-network -- pip install requests
```

**Example: Running a test suite and ensuring it doesn't create/delete files.**

```bash
# The test runner can read files but cannot write or modify anything.
hermetic --fs-readonly -- pytest
```

-----

## Installation

```bash
pip install hermetic
```

-----

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
    # requests.get("[https://example.com](https://example.com)") # --> raises PolicyViolation

    # This is allowed because the domain is on the allow-list.
    return requests.get("[https://api.internal.com/data](https://api.internal.com/data)")

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
        # os.system("echo 'This will fail.'") # --> raises PolicyViolation

    # Subprocesses are allowed again
    os.system("echo 'Exited sandbox.'")

check_system()
```

-----

## Security Considerations & Limitations

`hermetic` is a powerful behavioral guardrail, not a cryptographic fortress. It operates by **monkey-patching** standard library modules at runtime.

  - **Effectiveness**: It is highly effective against non-malicious code with unintended side effects or against unsophisticated malware that doesn't anticipate this kind of sandboxing.
  - **Bypass**: A determined attacker or code specifically written to defeat `hermetic` **can bypass it**. Bypasses could include using `ctypes` to call libc directly (if not blocked by `--block-native`), undoing the monkey-patches, or importing modules in a non-standard way.
  - **Analogy**: Think of it as a locked door—it stops a casual intruder but not a determined one with a lock-picking set.

For high-security needs where the code is actively hostile, you should use stronger, kernel-level sandboxing solutions like **Docker**, **gVisor**, or **seccomp**. `hermetic` is best used as a defense-in-depth tool to limit the "blast radius" of buggy or untrusted *Python code*.

-----

## Prior Art

This technique of monkey-patching for isolation is well-established, particularly in the testing ecosystem.

  - [pytest-socket](https://pypi.org/project/pytest-socket/): Disables sockets during tests.
  - [pytest-network](https://pypi.org/project/pytest-network/): Disables networking during tests.

For stronger sandboxing, consider:

  - [pysandbox](https://github.com/vstinner/pysandbox): Uses Linux `seccomp` for kernel-level syscall filtering.
  - [RestrictedPython](https://pypi.org/project/RestrictedPython/): Rewrites Python AST to enforce constraints.
  - [Docker](https://www.docker.com/): OS-level virtualization.
