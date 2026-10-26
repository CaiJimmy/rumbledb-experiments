#!/usr/bin/env python3
"""Times n lookups with map:get in a map of 512,000 entries, built once with map:merge, on each version of
versions.csv; see benchkit/benchkit.py for the options. LOOKUP_QUERY=queries/lookup-scattered.xq.template looks
up the keys in a scattered order instead of in key order.

Usage: [LOOKUP_QUERY=...] python3 run.py --mode jvm [--versions layered,compacted-initial,compacted,trie] [--ns 1,10000000] [--processes 3] [--run-dir NEW_DIRECTORY]
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "benchkit"))
import benchkit

# Every value is 1, so the sum of n lookups is n.
BENCHMARK = benchkit.Benchmark(query=os.environ.get("LOOKUP_QUERY", "queries/lookup.xq.template"), expected=str,
                               default_ns="1,10000000", work=lambda n: n, work_name="lookups")

if __name__ == "__main__":
    benchkit.main(BENCHMARK, HERE)
