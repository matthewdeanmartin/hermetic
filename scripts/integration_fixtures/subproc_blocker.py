import subprocess
import sys

from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation


def test_subproc():
    print("Attempting to run subprocess...")
    cmd = ["cmd", "/c", "echo hello"] if sys.platform == "win32" else ["echo", "hello"]
    subprocess.run(cmd, check=True, capture_output=True)
    print("Successfully ran subprocess")

print("--- Testing Subprocess Block ---")
try:
    with hermetic_blocker(block_subprocess=True):
        test_subproc()
except PolicyViolation:
    print("Subprocess: PolicyViolation caught as expected")
else:
    print("Subprocess: Error - PolicyViolation NOT caught")
    sys.exit(1)

print("\n--- Testing Subprocess Allow (default) ---")
with hermetic_blocker(block_subprocess=False):
    test_subproc()
    print("Subprocess Allow: Success")
