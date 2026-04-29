import sys

print("Attempting to execute eval...")
try:
    result = eval("1 + 1")
    print(f"Successfully executed eval: 1 + 1 = {result}")
except Exception as e:
    print(f"Failed to execute eval: {e}")
    sys.exit(1)

print("Attempting to execute exec...")
try:
    exec("a = 1 + 1")
    print("Successfully executed exec")
except Exception as e:
    print(f"Failed to execute exec: {e}")
    sys.exit(1)
