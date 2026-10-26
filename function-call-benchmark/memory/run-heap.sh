#!/usr/bin/env bash
# Largest observed heap after GC of local:fib(n) for every version: one command-line run per version and n with a GC log, and no
# histograms. Output in data/memory/heap/run-<UTC time>-<pid>/<version>-n<n>/; summarized by memory/heap.py.
# once is not run at n = 28: it runs out of memory after about 14 minutes (data/memory/once-n28/).
set -euo pipefail
cd "$(dirname "$0")/.."
export MEMORY_OUT="$PWD/data/memory/heap/run-$(date -u +%Y-%m-%dT%H%M%SZ)-$$"
mkdir -p "$(dirname "$MEMORY_OUT")"
mkdir "$MEMORY_OUT"
for n in 20 22 24 26; do
  for version in copy once plans final; do
    memory/run.sh "$version" "$n" 0
  done
done
for n in 28 30; do
  for version in plans final; do
    memory/run.sh "$version" "$n" 0
  done
done
python3 memory/heap.py --save "$MEMORY_OUT"
