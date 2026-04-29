import sys
import socket
from hermetic import hermetic_blocker
from hermetic.errors import PolicyViolation

def test_net(host="example.com"):
    print(f"Attempting to connect to {host}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((host, 80))
        print(f"Successfully connected to {host}")
        s.close()
    except PolicyViolation as e:
        print(f"FAIL: Blocked by Hermetic: {e}")
        raise
    except Exception as e:
        print(f"PASS: Not blocked by Hermetic (result: {e})")

print("--- Testing Context Manager ---")
try:
    with hermetic_blocker(block_network=True):
        test_net()
except PolicyViolation:
    print("Context Manager: PolicyViolation caught as expected")
else:
    print("Context Manager: Error - PolicyViolation NOT caught")
    sys.exit(1)

print("\n--- Testing Decorator ---")
@hermetic_blocker(block_network=True)
def decorated_test():
    test_net()

try:
    decorated_test()
except PolicyViolation:
    print("Decorator: PolicyViolation caught as expected")
else:
    print("Decorator: Error - PolicyViolation NOT caught")
    sys.exit(1)

print("\n--- Testing allow_localhost ---")
with hermetic_blocker(block_network=True, allow_localhost=True):
    test_net("127.0.0.1")
    print("Allow Localhost: Success")

print("\n--- Testing allow_domains ---")
with hermetic_blocker(block_network=True, allow_domains=["example.com"]):
    test_net("example.com")
    print("Allow Domain: Success")
