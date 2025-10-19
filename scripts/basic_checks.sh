#!/usr/bin/env bash
set -eou pipefail

hermetic_assert::expect_failure() {
  declare desc="Run a command and assert that it fails. Exit with error if it succeeds."
  declare -a cmd=("$@")

  if "${cmd[@]}"; then
    printf "ERROR: Command succeeded unexpectedly: %s\n" "${cmd[*]}" >&2
    return 1
  else
    printf "OK: Command failed as expected: %s\n" "${cmd[*]}" >&2
  fi
}

main() {
  # Block network; run httpie (same env)
  hermetic_assert::expect_failure hermetic --no-network -- http https://example.com

  # Allow only localhost; deny subprocess spawns
  # dire
  # hermetic_assert::expect_failure hermetic --no-network --allow-localhost --no-subprocess -- python usesubprocess.py

  # Foreign shebang test (pipx-installed httpie)
  hermetic_assert::expect_failure hermetic --no-network -- http https://example.com
}

main "$@"
