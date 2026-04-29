import os
import sys

from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation


def test_write(path="test_blocker.txt"):
    print(f"Attempting to write to {path}...")
    with open(path, "w") as f:
        f.write("test")
    print(f"Successfully wrote to {path}")
    if os.path.exists(path):
        os.remove(path)

def test_read(path="README.md"):
    print(f"Attempting to read from {path}...")
    with open(path, "r") as f:
        f.read(10)
    print(f"Successfully read from {path}")

print("--- Testing FS Readonly ---")
try:
    with hermetic_blocker(fs_readonly=True):
        test_write()
except PolicyViolation:
    print("FS Write: PolicyViolation caught as expected")
else:
    print("FS Write: Error - PolicyViolation NOT caught")
    sys.exit(1)

print("\n--- Testing FS Root Constraint ---")
# Use current directory as root for this test
root = os.getcwd()
with hermetic_blocker(fs_readonly=True, fs_root=root):
    test_read("README.md")
    print("FS Root Read Inside: Success")

try:
    # Try to read something definitely outside (if possible, or just non-existent outside root logic)
    # Actually, Hermetic's _within check is what we test.
    parent_readme = os.path.join("..", "README.md")
    with hermetic_blocker(fs_readonly=True, fs_root=os.path.join(root, "scripts")):
        test_read("README.md") # README.md is in root, but we restricted to root/scripts
except PolicyViolation:
    print("FS Root Read Outside: PolicyViolation caught as expected")
else:
    print("FS Root Read Outside: Error - PolicyViolation NOT caught")
    sys.exit(1)
