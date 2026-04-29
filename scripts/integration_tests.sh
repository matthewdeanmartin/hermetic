#!/usr/bin/env bash
# scripts/integration_tests.sh - Programmatic API tests for hermetic
set -uo pipefail

# Configuration
export PYTHONPATH="."
PYTHON="uv run python"
FIXTURES="scripts/integration_fixtures"

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
printf "Running Hermetic Integration Checks (Programmatic API)...\n"
printf "========================================================\n"

run_integration_test() {
    local desc="$1"
    local script="$2"
    TOTAL=$((TOTAL + 1))
    printf "TEST: %-60s " "$desc"
    # Run command and capture output
    if $PYTHON "$FIXTURES/$script" > /dev/null 2>&1; then
        printf "${GREEN}PASS${NC}\n"
    else
        printf "${RED}FAIL${NC}\n"
        FAILED=$((FAILED + 1))
    fi
}

run_integration_test "Network Blocker (Context/Decorator/Allow)" "net_blocker.py"
run_integration_test "Subprocess Blocker" "subproc_blocker.py"
run_integration_test "Filesystem Blocker (Readonly/Root)" "fs_blocker.py"
run_integration_test "Environment Blocker" "env_blocker.py"
run_integration_test "Code Execution Blocker" "code_exec_blocker.py"
run_integration_test "Interpreter Mutation Blocker" "interpreter_blocker.py"
run_integration_test "Native Extension Blocker" "native_blocker.py"
run_integration_test "Deny Import Blocker" "deny_import_blocker.py"

printf "========================================================\n"
if [ "$FAILED" -eq 0 ]; then
    printf "${GREEN}Summary: $TOTAL tests, all passed!${NC}\n"
    exit 0
else
    printf "${RED}Summary: $TOTAL tests, $FAILED failed.${NC}\n"
    exit 1
fi
