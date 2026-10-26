#!/bin/sh
# Runs the latency benchmark in three independent server processes per configuration, alternating
# the order of the configurations between rounds, as the RumbleDB benchmarks alternate versions.
# Results: <out>/round-<n>-<off|on>.json. Analyze them with analyze-latency.mjs <out>.
#
# Usage: sh run-latency.sh [out-dir] [configurations]   (defaults: data/latency "off on")
#
# Build the language server first (jsoniq-lsp/packages/language-server: pnpm run build).
set -e
cd "$(dirname "$0")"
OUT=${1:-data/latency}
CONFIGURATIONS=${2:-off on}
REVERSED=$(echo "$CONFIGURATIONS" | awk '{ for (i = NF; i > 0; i--) printf "%s ", $i }')
mkdir -p "$OUT"

for round in 1 2 3; do
    order=$CONFIGURATIONS
    [ "$round" = 2 ] && order=$REVERSED
    for wrapper in $order; do
        echo "round $round, wrapper $wrapper: $(date +%H:%M:%S)"
        node latency.mjs "$wrapper" "$OUT/round-$round-$wrapper.json"
    done
done
echo "done: $(date +%H:%M:%S)"
