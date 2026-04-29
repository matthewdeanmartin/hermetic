import sys

from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation


def test_interp_mutation():
    print("Attempting to modify sys.path...")
    sys.path.append("/tmp/test")

print("--- Testing Interpreter Mutation Block ---")
try:
    with hermetic_blocker(block_interpreter_mutation=True):
        test_interp_mutation()
except PolicyViolation:
    print("Interpreter Mutation: PolicyViolation caught as expected")
else:
    print("Interpreter Mutation: Error - PolicyViolation NOT caught")
    sys.exit(1)
