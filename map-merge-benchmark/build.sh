#!/usr/bin/env bash
# Builds jars/<name>.jar for every version in versions.csv; see benchkit/build.sh. jars/ is a link to
# ../map-benchmark/jars, so ../map-benchmark/build.sh builds these jars too.
# Usage: ./build.sh [path to RumbleDB repository] [names]   (default: ../../rumble, all versions)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/../benchkit/build.sh" "$HERE" "$@"
