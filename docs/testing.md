# Testing Patterns

Hermetic's most uncontroversial use is in unit testing: guarantee
that a test really is hermetic, not just hermetic-on-this-laptop.
This page collects patterns for using hermetic in `pytest` and
similar frameworks.

## A pytest fixture for "no network"

```python
# conftest.py
import pytest
from hermetic import hermetic_blocker

@pytest.fixture
def no_network():
    with hermetic_blocker(block_network=True, allow_localhost=True):
        yield

# tests/test_thing.py
def test_works_offline(no_network):
    # If anything in here calls out to the internet, the test fails
    # loudly with PolicyViolation.
    result = my_module.compute()
    assert result == 42
```

`allow_localhost=True` lets you keep using a local test database,
a wiremock server, or `httpbin` running on `127.0.0.1`.

## A session-scoped guard for the whole test run

```python
# conftest.py
import pytest
from hermetic import hermetic_blocker

@pytest.fixture(scope="session", autouse=True)
def _no_network_for_this_test_run():
    with hermetic_blocker(block_network=True, allow_localhost=True):
        yield
```

Now every test in the session runs with the network guard. Any
test that needs the real network has to override the fixture or
use a `pytest.mark.skip` plus a conditional.

## Allow-listing specific external APIs

If you have a small set of trusted endpoints (a captive
mock-OAuth server, a fixed staging API), allow-list them:

```python
@pytest.fixture
def constrained_network():
    with hermetic_blocker(
        block_network=True,
        allow_localhost=True,
        allow_domains=["staging.api.example.com"],
    ):
        yield
```

## Catching `PolicyViolation` in a test

If your test wants to *verify* that the code under test would
have made a network call (rather than swallowing the call
silently), catch the exception:

```python
import pytest
from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation

def test_module_calls_out_to_api():
    with hermetic_blocker(block_network=True):
        with pytest.raises(PolicyViolation, match="api.example.com"):
            my_module.refresh_from_api()
```

This is a stronger assertion than mocking `requests.get`: you're
asserting the code reached the network *layer*, not just the
HTTP client.

## Comparison with `pytest-socket` / `pytest-network`

Both of those plugins do something similar (patch socket-level
APIs to disable connections during tests). Hermetic differs in:

- **Scope.** Hermetic also covers subprocess, filesystem, and
  native imports — useful when you want a multi-axis sandbox in
  one place.
- **Bootstrap.** Hermetic can be invoked from the command line
  to wrap an entire process tree, not just a `pytest` run. So
  the same tool serves both unit-test and CLI-runner use cases.
- **Allow-list semantics.** Hermetic supports suffix-match
  domain allow-lists, localhost, and a non-overridable cloud
  metadata deny-list.

If you only need socket-level test isolation, `pytest-socket`
is smaller and well-trodden. If you need anything else, hermetic
gives you the same primitive plus more.

## Testing a CLI tool inside its own test suite

If you ship a tool and want to verify it's hermetic-clean, you
can run its tests under hermetic in CI:

```yaml
# .github/workflows/test.yml
- run: pip install -e . hermetic-seal pytest
- run: hermetic --no-network --allow-localhost -- pytest tests/
```

Any test that makes an unmarked external request fails the
build.

## Catching writes outside a sandbox

```python
import pytest
from hermetic import hermetic_blocker

@pytest.fixture
def sandboxed(tmp_path):
    with hermetic_blocker(fs_readonly=True, fs_root=str(tmp_path)):
        yield tmp_path

def test_module_only_writes_to_sandbox(sandboxed):
    # The function is supposed to keep all its IO inside `sandboxed`.
    # If it tries to write anywhere else (or read /etc/passwd), it
    # raises PolicyViolation.
    my_module.process(workdir=sandboxed)
```

Note: `fs_readonly=True` denies *all* writes including ones to
`fs_root`. If you need writes inside the root, hermetic doesn't
support that today — you want a read-only sandbox plus an
allow-write subdirectory, which would require a more elaborate
guard. For now, isolate writes via the OS (use a tmpfs, a
container bind mount, or just `tmp_path` and assert manually).

## Combining with property-based tests

Hypothesis tests and hermetic compose cleanly:

```python
from hypothesis import given, strategies as st
from hermetic import hermetic_blocker

@given(st.text())
def test_pure_function_is_pure(s):
    with hermetic_blocker(block_network=True, block_subprocess=True):
        result = my_module.transform(s)
        # If `transform` is pure, this never raises and the only
        # variability is the input.
        assert isinstance(result, str)
```

If a Hypothesis-generated example causes the code to take a
non-pure path (open a file, hit the network), the test fails
deterministically with `PolicyViolation`.
