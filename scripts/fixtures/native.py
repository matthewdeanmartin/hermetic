import sys

print("Attempting to import native module...")
try:
    import ctypes

    # Reference the module so linters/autoflake never strip the import:
    # without an actual native import here, the --block-native guard has
    # nothing to block and the smoke test silently passes.
    print(f"Successfully imported ctypes ({ctypes.__name__})")
except Exception as e:
    print(f"Failed to import ctypes: {e}")
    sys.exit(1)
