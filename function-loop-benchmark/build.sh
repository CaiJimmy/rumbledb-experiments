#!/usr/bin/env bash
# Builds jars/<name>.jar for every version in versions.csv; see benchkit/build.sh. jars/ is a link to
# ../function-call-benchmark/jars, which has the same versions, so this builds the jars of both benchmarks.
# Usage: ./build.sh [path to RumbleDB repository]   (default: ../../rumble)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/../benchkit/build.sh" "$HERE" "$@"
