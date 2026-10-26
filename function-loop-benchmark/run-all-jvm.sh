#!/usr/bin/env bash
# The query alone, timed inside the JVM, with the bytes it allocates: 3 processes per version and n, each with
# 2 untimed warm-up runs and 5 timed runs, versions interleaved; 12 GB of driver memory. copy (about 820 us per
# call) stops at n = 10000, since it overflows the stack at n = 30000 (see README.md).
set -euo pipefail
cd "$(dirname "$0")"
OUT="data/jvm/run-$(date -u +%Y-%m-%dT%H%M%SZ)-$$"
python3 run.py --mode jvm --versions copy,once,plans,final --ns 10000,30000,100000,300000,1000000 \
  --max-n copy=10000 --processes 3 --warmups 2 --iterations 5 --driver-memory 12g --timeout 3600 --run-dir "$OUT/main"
python3 analyze.py --save "$OUT"
