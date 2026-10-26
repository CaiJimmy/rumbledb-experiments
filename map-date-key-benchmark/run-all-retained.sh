#!/usr/bin/env bash
# The memory of the built map, as in ../map-benchmark/run-all-retained.sh: 3 processes per version and n, each
# with 1 untimed warm-up run and 2 measured runs, versions interleaved; 4 GB of driver memory.
set -euo pipefail
cd "$(dirname "$0")"
OUT="data/retained/run-$(date -u +%Y-%m-%dT%H%M%SZ)-$$"
python3 run.py --mode retained --versions trie,trie-hashed --ns 1,1000,4000,16000,32000,64000 --max-n trie=32000 \
  --processes 3 --warmups 1 --iterations 2 --driver-memory 4g --timeout 3600 --run-dir "$OUT/main"
python3 analyze.py --save "$OUT"
