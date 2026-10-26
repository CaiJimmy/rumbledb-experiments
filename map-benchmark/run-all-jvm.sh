#!/usr/bin/env bash
# The query alone, timed inside the JVM, with the bytes it allocates: 3 processes per version and n, each
# with 2 untimed warm-up runs and 5 timed runs, versions interleaved; 4 GB of driver memory. layered stops at
# n = 4000, compacted-initial and compacted at n = 64000; only trie continues to n = 512000.
set -euo pipefail
cd "$(dirname "$0")"
OUT="data/jvm/run-$(date -u +%Y-%m-%dT%H%M%SZ)-$$"
python3 run.py --mode jvm --versions layered,compacted-initial,compacted,trie \
  --ns 1000,2000,4000,8000,16000,32000,64000,128000,256000,512000 --max-n layered=4000,compacted-initial=64000,compacted=64000 \
  --processes 3 --warmups 2 --iterations 5 --driver-memory 4g --timeout 3600 --run-dir "$OUT/main"
python3 analyze.py --save "$OUT"
