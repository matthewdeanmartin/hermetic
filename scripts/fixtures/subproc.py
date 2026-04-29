import subprocess
import sys

print("Attempting to run subprocess...")
try:
    # Use a command that exists on most systems
    cmd = ["cmd", "/c", "echo hello"] if sys.platform == "win32" else ["echo", "hello"]
    subprocess.run(cmd, check=True, capture_output=True)
    print("Successfully ran subprocess")
except Exception as e:
    print(f"Failed to run subprocess: {e}")
    sys.exit(1)
