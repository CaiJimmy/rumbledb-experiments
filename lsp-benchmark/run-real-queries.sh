#!/bin/sh
# Response times on real queries and cold start, with the method of the RumbleDB benchmarks:
# - real queries: 3 server processes per configuration in alternating order, each with 2 warm-up
#   passes and 5 timed passes over all valid test queries;
# - cold start: 10 new server processes per configuration, alternating; a cold start happens once
#   per process, so it has no warm-up.
# Results: <out>/real-<n>-<off|on>.json and <out>/cold-<n>-<off|on>.json.
# Analyze them with analyze-real-queries.mjs <out>.
set -e
cd "$(dirname "$0")"
OUT=${1:-data/real-queries}
mkdir -p "$OUT"

for round in 1 2 3; do
    order="off on"
    [ "$round" = 2 ] && order="on off"
    for wrapper in $order; do
        echo "real queries, round $round, wrapper $wrapper: $(date +%H:%M:%S)"
        node real-queries.mjs "$wrapper" "$OUT/real-$round-$wrapper.json"
    done
done

for round in 1 2 3 4 5 6 7 8 9 10; do
    order="off on"
    [ $((round % 2)) = 0 ] && order="on off"
    for wrapper in $order; do
        ROUNDS=1 node cold-start.mjs "$wrapper" "$OUT/cold-$round-$wrapper.json"
    done
done
echo "done: $(date +%H:%M:%S)"
