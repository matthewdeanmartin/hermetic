import sys
from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation

def test_code_exec():
    print("Attempting to execute eval...")
    eval("1+1")

print("--- Testing Code Exec Block ---")
try:
    with hermetic_blocker(block_code_exec=True):
        test_code_exec()
except PolicyViolation:
    print("Code Exec: PolicyViolation caught as expected")
else:
    print("Code Exec: Error - PolicyViolation NOT caught")
    sys.exit(1)
