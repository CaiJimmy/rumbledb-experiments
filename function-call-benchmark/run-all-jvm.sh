#!/usr/bin/env bash
# The query alone, timed inside the JVM, with the bytes it allocates: 3 processes per version and n, each with
# 2 untimed warm-up runs and 5 timed runs, versions interleaved; 12 GB of driver memory. copy and once stop at
# n = 26 (once runs out of memory at n = 28). copy at n = 28 and 30 takes 8 and 21 minutes per run, so it runs
# in 1 process with 1 warm-up run and 3 timed runs, with a timeout of 3 hours.
set -euo pipefail
cd "$(dirname "$0")"
OUT="data/jvm/run-$(date -u +%Y-%m-%dT%H%M%SZ)-$$"
python3 run.py --mode jvm --versions copy,once,plans,final --ns 18,20,22,24,26,28,30 --max-n copy=26,once=26 \
  --processes 3 --warmups 2 --iterations 5 --driver-memory 12g --timeout 3600 --run-dir "$OUT/main"
python3 run.py --mode jvm --versions copy --ns 28,30 \
  --processes 1 --warmups 1 --iterations 3 --driver-memory 12g --timeout 10800 --run-dir "$OUT/large-copy"
python3 analyze.py --save "$OUT"
