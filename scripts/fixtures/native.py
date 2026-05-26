import sys

print("Attempting to import native module...")
try:

    print("Successfully imported ctypes")
except Exception as e:
    print(f"Failed to import ctypes: {e}")
    sys.exit(1)
