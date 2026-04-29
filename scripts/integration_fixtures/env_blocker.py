import sys
import os
from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation

def test_env_read():
    print("Attempting to read environment...")
    val = os.environ.get("PATH")
    print(f"PATH: {val[:20]}...")

def test_env_write():
    print("Attempting to write environment...")
    os.environ["HERMETIC_TEST"] = "1"

print("--- Testing Environment Block ---")
try:
    with hermetic_blocker(block_environment=True):
        test_env_read()
except PolicyViolation:
    print("Env Read: PolicyViolation caught as expected")
else:
    print("Env Read: Error - PolicyViolation NOT caught")
    sys.exit(1)

try:
    with hermetic_blocker(block_environment=True):
        test_env_write()
except PolicyViolation:
    print("Env Write: PolicyViolation caught as expected")
else:
    print("Env Write: Error - PolicyViolation NOT caught")
    sys.exit(1)
