import os
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "test_file.txt"
print(f"Attempting to write to {path}...")
try:
    with open(path, "w") as f:
        f.write("test")
    print(f"Successfully wrote to {path}")
    if os.path.exists(path):
        os.remove(path)
except Exception as e:
    print(f"Failed to write to {path}: {e}")
    sys.exit(1)
