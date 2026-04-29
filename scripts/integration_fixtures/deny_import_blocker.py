import sys

from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation


def test_deny_import():
    print("Attempting to import math...")
    import math

print("--- Testing Deny Import ---")
try:
    with hermetic_blocker(deny_imports=["math"]):
        test_deny_import()
except PolicyViolation:
    print("Deny Import: PolicyViolation caught as expected")
else:
    print("Deny Import: Error - PolicyViolation NOT caught")
    sys.exit(1)
