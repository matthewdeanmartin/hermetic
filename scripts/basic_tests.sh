# Block network; run httpie (same env)
hermetic --no-network -- http https://example.com

# Allow only localhost; deny subprocess spawns
hermetic --no-network --allow-localhost --no-subprocess -- python usesubprocess.py

# Readonly FS with explicit read root; strict imports
hermetic --fs-readonly=./sandbox --strict-imports -- target-cli --opt

# pipx-installed httpie (foreign interpreter):
# hermetic detects foreign shebang and injects a sitecustomize bootstrap
hermetic --no-network -- http https://example.com
