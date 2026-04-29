import sys

module_name = sys.argv[1] if len(sys.argv) > 1 else "math"
print(f"Attempting to import {module_name}...")
try:
    __import__(module_name)
    print(f"Successfully imported {module_name}")
except Exception as e:
    print(f"Failed to import {module_name}: {e}")
    sys.exit(1)
