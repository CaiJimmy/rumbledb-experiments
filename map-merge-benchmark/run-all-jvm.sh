#!/usr/bin/env bash
# The query alone, timed inside the JVM, with the bytes it allocates: 3 processes per version and n, each with
# 2 untimed warm-up runs and 5 timed runs, versions interleaved; 4 GB of driver memory.
set -euo pipefail
cd "$(dirname "$0")"
OUT="data/jvm/run-$(date -u +%Y-%m-%dT%H%M%SZ)-$$"
python3 run.py --mode jvm --versions compacted,trie --ns 1000,512000 \
  --processes 3 --warmups 2 --iterations 5 --driver-memory 4g --timeout 3600 --run-dir "$OUT/main"
python3 analyze.py --save "$OUT"
