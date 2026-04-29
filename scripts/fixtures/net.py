import socket
import sys

target_host = sys.argv[1] if len(sys.argv) > 1 else "example.com"
if "://" in target_host:
    from urllib.parse import urlparse
    target_host = urlparse(target_host).hostname or target_host

print(f"Attempting to connect to {target_host}...")
try:
    # Use socket.connect directly with the hostname.
    # This avoids early resolution to IP in many cases.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    s.connect((target_host, 80))
    print(f"Successfully connected to {target_host}")
    s.close()
except Exception as e:
    err_msg = str(e)
    print(f"Connect result for {target_host}: {err_msg}")
    if "network disabled" in err_msg or "import blocked" in err_msg:
        print("FAIL: Blocked by Hermetic")
        sys.exit(1)
    
    # If it's another error (like timeout or connection refused), 
    # it means Hermetic ALLOWED it.
    print(f"PASS: Not blocked by Hermetic (result: {err_msg})")
    sys.exit(0)
