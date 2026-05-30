import sys

from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation


def test_native_import():
    print("Attempting to import ctypes...")
    import ctypes

    # Reference the import so linters/autoflake never strip it; without an
    # actual import the block_native guard has nothing to fire on.
    print(ctypes.__name__)


print("--- Testing Native Block ---")
try:
    with hermetic_blocker(block_native=True):
        test_native_import()
except PolicyViolation:
    print("Native Import: PolicyViolation caught as expected")
else:
    print("Native Import: Error - PolicyViolation NOT caught")
    sys.exit(1)
