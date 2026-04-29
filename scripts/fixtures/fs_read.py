import sys
import os

path = sys.argv[1] if len(sys.argv) > 1 else "example1.py"
print(f"Attempting to read from {path}...")
try:
    with open(path, "r") as f:
        content = f.read(10)
    print(f"Successfully read from {path}: {content!r}")
except Exception as e:
    print(f"Failed to read from {path}: {e}")
    sys.exit(1)
