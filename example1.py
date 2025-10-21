from hermetic import hermetic_blocker


@hermetic_blocker(block_network=True)
def make_request() -> None:
    import socket
    socket.getaddrinfo("example.com", 80)


make_request()

with hermetic_blocker(block_subprocess=True):
    import subprocess

    result = subprocess.run(["bash", "echo", "hello"], capture_output=True, text=True)
    assert result.returncode == 0
