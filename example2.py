from hermetic import hermetic_blocker

with hermetic_blocker(block_subprocess=True):
    import subprocess

    result = subprocess.run(["bash", "echo", "hello"], capture_output=True, text=True)
    assert result.returncode == 0
