# Network Guard

Activated by `--no-network` (CLI) or `block_network=True` (API).
Implemented in `hermetic/guards/network.py`.

## What it patches

| Surface | What happens |
|---|---|
| `socket.socket` | Replaced with `GuardedSocket`, a subclass that vetoes outbound `connect`, `connect_ex`, `sendto`, `sendmsg`, and non-loopback `bind`. |
| `socket.SocketType` | Aliased to `GuardedSocket` for libraries that import the type alias. |
| `socket.create_connection` | Wrapped — checks the host before dialing. |
| `socket.getaddrinfo` | Wrapped — DNS for a non-allowlisted host raises. |
| `socket.gethostbyname`, `gethostbyname_ex` | Wrapped — same. |
| `socket.socketpair`, `socket.fromfd`, `socket.fromshare` | Hard-blocked (defense against fd-resurrection bypasses). |
| `ssl.SSLContext.wrap_socket` | Hard-blocked. |

## Allow-listing

Two knobs control what is permitted through the guard:

### `--allow-localhost` / `allow_localhost=True`

Permits connections to `127.0.0.1`, `::1`, `localhost`, and `0.0.0.0`.
Without this flag, even loopback is denied.

### `--allow-domain DOMAIN` / `allow_domains=["DOMAIN"]`

Permits connections to a specific host. Matching is **suffix-based**:

- `--allow-domain example.com` allows `example.com` and `*.example.com`.
- It does **not** allow `example.com.attacker.example` (attacker-controlled
  suffix) — the match is anchored to the dot boundary.
- It does **not** allow `notexample.com` (no shared suffix).

Multiple domains: pass `--allow-domain` repeatedly, or pass a list to
the API.

### Always denied: cloud metadata

These hosts are denied even if you allow-list them:

- `169.254.169.254` (AWS / Azure / OpenStack / DigitalOcean)
- `metadata.google.internal`, `metadata` (GCP)
- `fd00:ec2::254`, `fd00:ec2:0:0:0:0:0:254` (AWS IMDSv2 IPv6)
- `fe80::a9fe:a9fe` (link-local SLAAC variant)
- `100.100.100.200` (Alibaba Cloud)

The motivation is credential exfiltration in cloud CI: hostile code
that finds a way past the network guard for a normal host should not
be able to grab IAM credentials from the metadata service.

## What it does *not* catch

A few honest limitations, kept here so you can decide whether to pair
hermetic with a stronger sandbox:

- **`_socket.socket` direct construction**. The C-level base class is
  not patched — if it were, `socket.socket.__init__` would recurse
  infinitely. Code that does `import _socket; _socket.socket(...)`
  gets a raw socket. The patched `getaddrinfo`/`create_connection`
  surface still applies, so the attacker also has to do their own
  DNS, which is blocked.
- **Captured class references**. A library that did `from socket
  import socket` *before* hermetic installed has the original class
  in its module dict. If it instantiates that, it bypasses
  `GuardedSocket`. Most stdlib (and most well-known third-party)
  modules look up `socket.socket` lazily, but not all.
- **DoH (DNS-over-HTTPS)** through an allow-listed domain. If you
  allow-list a CDN that fronts a public DoH resolver, an attacker
  can resolve any host through it. Out of scope.

See [Threat Model](../threat-model.md) for the full enumeration.

## Tracing

With `--trace`, blocked calls write one line each to stderr:

```text
[hermetic] blocked socket.connect host=example.com reason=no-network
[hermetic] blocked socket.getaddrinfo host=example.com reason=no-network
[hermetic] blocked socket.bind host=0.0.0.0 reason=no-network
```

Hosts are not redacted — they're the addresses the calling code
chose, and the user already knows them. If your allow-list contains
secrets, don't enable `--trace`.

## Examples

Block everything, including localhost:

```bash
hermetic --no-network -- python -c "import urllib.request; urllib.request.urlopen('https://example.com')"
```

Block everything except localhost (typical test setup):

```bash
hermetic --no-network --allow-localhost -- pytest tests/
```

Allow one external API:

```bash
hermetic --no-network --allow-domain api.openai.com -- python my_agent.py
```

Allow a private CIDR via its DNS name (you cannot allow-list raw
IP ranges; use a hostname):

```bash
hermetic --no-network --allow-domain internal.company.local -- my_app
```
