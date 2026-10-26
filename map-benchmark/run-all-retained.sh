#!/usr/bin/env bash
# The memory of the built map: QueryBench keeps the map alive and measures the heap after a full garbage
# collection, minus the heap before the query. 3 processes per version and n, each with 1 untimed warm-up run
# and 2 measured runs, versions interleaved; 4 GB of driver memory. The same n as run-all-jvm.sh.
set -euo pipefail
cd "$(dirname "$0")"
OUT="data/retained/run-$(date -u +%Y-%m-%dT%H%M%SZ)-$$"
python3 run.py --mode retained --versions layered,compacted-initial,compacted,trie \
  --ns 1,1000,2000,4000,8000,16000,32000,64000,128000,256000,512000 --max-n layered=4000,compacted-initial=64000,compacted=64000 \
  --processes 3 --warmups 1 --iterations 2 --driver-memory 4g --timeout 3600 --run-dir "$OUT/main"
python3 analyze.py --save "$OUT"
