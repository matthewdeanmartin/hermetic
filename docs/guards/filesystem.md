# Filesystem Guard

Activated by `--fs-readonly[=ROOT]` (CLI) or `fs_readonly=True`
(plus optional `fs_root=...`) in the API. Implemented in
`hermetic/guards/filesystem.py`.

## What it patches

### Read paths

These are wrapped to enforce both write-denial and (if `fs_root` is
set) root-containment on **read**:

| Surface | Patched |
|---|---|
| `builtins.open` | Yes |
| `io.open` | Yes (alias of `builtins.open` on CPython, but third-party libs sometimes import this directly) |
| `os.open` | Yes — flags are inspected; any of `O_WRONLY`, `O_RDWR`, `O_APPEND`, `O_CREAT`, `O_TRUNC` is treated as a write |
| `posix.open` (POSIX) / `nt.open` (Windows) | Yes — the C-level alias |
| `pathlib.Path.open` | Yes |

### Write paths (always denied when `fs_readonly=True`)

| Module | Functions patched |
|---|---|
| `os` | `remove`, `rename`, `replace`, `unlink`, `rmdir`, `mkdir`, `makedirs`, `chmod`, `chown`, `link`, `symlink`, `truncate`, `utime` |
| `pathlib.Path` | `chmod`, `hardlink_to`, `mkdir`, `rename`, `replace`, `rmdir`, `symlink_to`, `touch`, `unlink` |
| `shutil` | `rmtree`, `move`, `copy`, `copy2`, `copyfile`, `copytree`, `chown`, `make_archive`, `unpack_archive` |

`shutil`'s mutators ultimately go through `os.*` in CPython, which
is already patched. The direct patch is defense-in-depth against
vendored or alternate `shutil` implementations.

## Mode-string rules for `open()`

Hermetic detects writes by inspecting the mode string for any of
`w`, `a`, `x`, `+`. So:

| Mode | Treatment |
|---|---|
| `"r"`, `"rb"`, `"rt"` | Read |
| `"w"`, `"wb"`, `"a"`, `"a+"`, `"r+"`, `"x"` | Write — denied |

If `mode` is omitted, `"r"` is assumed (matching `open`'s default).

For `os.open`, hermetic translates the integer flags to a mode by
checking the write-flag bitmask, then re-uses the same string-based
check.

## Sandbox root

When you pass `--fs-readonly=ROOT` (or `fs_root="ROOT"` in the API),
**reads are also constrained**:

- The path is normalized via `os.path.realpath` (so symlinks are
  resolved before the check).
- The resolved path must equal `ROOT` or live under `ROOT + os.sep`.
- Both relative and absolute `ROOT` values work; relative is
  resolved against the CWD at install time.

```bash
hermetic --fs-readonly=./sandbox -- python run.py
```

Inside `run.py`:

```python
open("./sandbox/data.txt")              # OK
open("/etc/passwd")                     # raises PolicyViolation
open("./sandbox/../outside.txt")        # raises (normalized path escapes)
```

Symlinks inside the sandbox that point outside are blocked because
`realpath` resolves them before the containment check.

## What it does *not* catch

- **Symlink racing** between `realpath` and `open`. Hermetic does
  not implement TOCTOU-safe path checks. A pre-existing race is
  unlikely in real Python code; an attacker pre-staging a symlink
  inside the root is the realistic risk.
- **`scandir` / `listdir` results outside the root**. Currently only
  the *open path* is constrained, not the names returned by
  directory listings. Reading the *contents* of any returned path
  is constrained — but the attacker may learn that certain files
  exist.
- **Memory-mapped files via `mmap`**. `mmap.mmap` requires an
  already-open file descriptor (which goes through `os.open` and
  is therefore checked), so this is mostly fine — but the post-mmap
  page modifications are not guarded.
- **C extensions that call `open(2)` directly**. Out of scope by
  construction; pair with `--block-native` if this matters to you.

## Tracing

```text
[hermetic] blocked open write path=/tmp/x
[hermetic] blocked open read-outside-root path=/etc/passwd
[hermetic] blocked fs mutation
```

## Examples

Read-only everywhere:

```bash
hermetic --fs-readonly -- python my_analysis.py
```

Read-only and confined to a workspace:

```bash
hermetic --fs-readonly=./workspace -- python my_analysis.py
```

Combine with network and subprocess for an LLM tool sandbox:

```bash
hermetic \
    --no-network --allow-domain api.anthropic.com \
    --no-subprocess \
    --fs-readonly=./agent-workspace \
    --block-native \
    -- python run_agent.py
```
