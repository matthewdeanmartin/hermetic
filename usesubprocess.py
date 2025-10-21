import sys

try:
    print("prep to run")
    import subprocess
    subprocess.run(['bash', '-c', 'echo'])
    print("Shouldn't be here")
except Exception:
    sys.exit(100)