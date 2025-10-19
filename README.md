# hermetic

Run a python tool with certain APIs disabled

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




