# hermetic

Run a python tool, or your application with certain APIs disabled, such as network or subprocess.

The previously safe library you depend on was highjacked and will be sending your password files to a remote server.
Or you installed this and the malicious hackers didn't include evasive code to defeat this fig leaf of a security
feature and the day is saved.

If Alice and Bob know about your application and specifically are targeting this, this tool won't help.

## Usage

CLI for 3rd party pure python CLI apps

```bash
hermetic --no-network -- http https://example.com
```

For your own app with 3rd party libraries

```python
from hermetic import with_hermetic


@with_hermetic(block_network=True, allow_localhost=True)
def main():
    ...
```

## Where could this work?

There are APIs you don't need but an application or 3rd party library you depend on needs. So you block them.

The 3rd party library must be unaware of hermetic or monkeypatching. Import order is important, hermetic must run
early enough to intercept all imports to the banned API. Then use of the banned API is blocked and the whole app stops.

This already works in unit testing where there isn't an adversarial relationship between the developers testing the code
and writing the code under test, where you block network traffic to guarantee a unit test is pure of network side
effects.

## Is this defeatable?

Yes, by many routes. Native code, import order tricks, undoing a monkey patch, bringing along a vendorized copy of APIs,
and so on.

This is "envelope instead of postcard" level security. This is "lock your door with standard key that can be picked with
a $5 purchase on Ebay" level security.

Real sandboxing is running your code in a docker container.

## Prior Art

Tools using same technique
- [pytest-socket](https://pypi.org/project/pytest-socket)
- [pytest-network](https://pypi.org/project/pytest-network/) - Disables library.

Other strong standboxes
- [pysandbox](https://github.com/vstinner/pysandbox)  - [Seccomp](https://en.wikipedia.org/wiki/Seccomp) sandboxing
- [RestrictedPython](https://pypi.org/project/RestrictedPython/)
- Docker
- [Pyscript](https://pyscript.net/)



