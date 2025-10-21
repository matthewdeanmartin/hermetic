#!/usr/bin/env bash
set -eou pipefail

hermetic --no-network -- http https://example.com
