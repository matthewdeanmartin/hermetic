import sys

print("Attempting to modify sys.path...")
try:
    sys.path.append("/tmp/hermetic_test_path")
    print("Successfully modified sys.path")
except Exception as e:
    print(f"Failed to modify sys.path: {e}")
    sys.exit(1)
