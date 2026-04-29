#!/usr/bin/env bash
# scripts/basic_checks.sh - Comprehensive bash tests for hermetic
set -uo pipefail

# Configuration
export PYTHONPATH="."
HERMETIC="uv run hermetic"
FIXTURES="scripts/fixtures"
PYTHON="python" # Use the python in the current environment

TOTAL=0
FAILED=0

# Use color if attached to a terminal
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    NC=''
fi

# Print a nice header
printf "Running Hermetic Basic Checks...\n"
printf "================================\n"

assert_fail() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    printf "TEST: %-60s " "$desc"
    # Run command and capture output
    if $HERMETIC "$@" > /dev/null 2>&1; then
        printf "${RED}FAIL${NC} (expected failure)\n"
        FAILED=$((FAILED + 1))
    else
        printf "${GREEN}PASS${NC}\n"
    fi
}

assert_pass() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    printf "TEST: %-60s " "$desc"
    # Run command and capture output
    if $HERMETIC "$@" > /dev/null 2>&1; then
        printf "${GREEN}PASS${NC}\n"
    else
        printf "${RED}FAIL${NC} (expected success)\n"
        FAILED=$((FAILED + 1))
    fi
}

# Network Tests
assert_fail "Block all network" --no-network -- $PYTHON "$FIXTURES/net.py" http://example.com
assert_pass "Allow localhost" --no-network --allow-localhost -- $PYTHON "$FIXTURES/net.py" http://127.0.0.1
assert_fail "Block non-localhost when localhost allowed" --no-network --allow-localhost -- $PYTHON "$FIXTURES/net.py" http://example.com
assert_pass "Allow specific domain" --no-network --allow-domain example.com -- $PYTHON "$FIXTURES/net.py" http://example.com
assert_fail "Block other domain when specific allowed" --no-network --allow-domain example.com -- $PYTHON "$FIXTURES/net.py" http://google.com

# Subprocess Tests
assert_fail "Block subprocess" --no-subprocess -- $PYTHON "$FIXTURES/subproc.py"
assert_pass "Allow subprocess (default)" -- $PYTHON "$FIXTURES/subproc.py"

# Filesystem Tests
assert_fail "Make filesystem readonly" --fs-readonly -- $PYTHON "$FIXTURES/fs.py" test_write.txt
assert_pass "Allow filesystem write (default)" -- $PYTHON "$FIXTURES/fs.py" test_write.txt

# Filesystem Root Tests
mkdir -p scripts/fixtures/sandbox
touch scripts/fixtures/sandbox/test.txt
assert_pass "Read inside FS root" --fs-readonly=scripts/fixtures/sandbox -- $PYTHON "$FIXTURES/fs_read.py" scripts/fixtures/sandbox/test.txt
assert_fail "Read outside FS root" --fs-readonly=scripts/fixtures/sandbox -- $PYTHON "$FIXTURES/fs_read.py" README.md
rm -rf scripts/fixtures/sandbox

# Environment Tests
assert_fail "Block environment" --no-environment -- $PYTHON "$FIXTURES/env.py"
assert_pass "Allow environment (default)" -- $PYTHON "$FIXTURES/env.py"

# Code Execution Tests
assert_fail "Block code exec (eval/exec)" --no-code-exec -- $PYTHON "$FIXTURES/code_exec.py"
assert_pass "Allow code exec (default)" -- $PYTHON "$FIXTURES/code_exec.py"

# Interpreter Mutation Tests
assert_fail "Block interpreter mutation" --no-interpreter-mutation -- $PYTHON "$FIXTURES/interpreter.py"
assert_pass "Allow interpreter mutation (default)" -- $PYTHON "$FIXTURES/interpreter.py"

# Native Extension Tests
assert_fail "Block native extensions" --block-native -- $PYTHON "$FIXTURES/native.py"
assert_pass "Allow native extensions (default)" -- $PYTHON "$FIXTURES/native.py"

# Deny Import Tests
assert_fail "Deny specific import (math)" --deny-import math -- $PYTHON "$FIXTURES/deny_import.py" math
assert_pass "Allow other import when one denied" --deny-import os -- $PYTHON "$FIXTURES/deny_import.py" math

# Profile Tests
assert_pass "Apply a profile (net-hermetic)" --profile net-hermetic -- $PYTHON "$FIXTURES/subproc.py"
assert_fail "Apply a profile (net-hermetic) blocks net" --profile net-hermetic -- $PYTHON "$FIXTURES/net.py" http://example.com
assert_fail "Apply a profile (block-all) blocks everything" --profile block-all -- $PYTHON "$FIXTURES/subproc.py"

# Cleanup
rm -f test_write.txt

printf "================================\n"
if [ "$FAILED" -eq 0 ]; then
    printf "${GREEN}Summary: $TOTAL tests, all passed!${NC}\n"
    exit 0
else
    printf "${RED}Summary: $TOTAL tests, $FAILED failed.${NC}\n"
    exit 1
fi
