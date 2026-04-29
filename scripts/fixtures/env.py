import os
import sys

print("Attempting to read environment...")
try:
    # Try to read PATH which should always exist
    val = os.environ.get("PATH")
    if val:
        print("Successfully read PATH")
    else:
        print("PATH not found or empty")
        # Some sandboxes might empty it
except Exception as e:
    print(f"Failed to read environment: {e}")
    sys.exit(1)

print("Attempting to write environment...")
try:
    os.environ["HERMETIC_TEST"] = "1"
    print("Successfully wrote environment")
except Exception as e:
    print(f"Failed to write environment: {e}")
    sys.exit(1)
