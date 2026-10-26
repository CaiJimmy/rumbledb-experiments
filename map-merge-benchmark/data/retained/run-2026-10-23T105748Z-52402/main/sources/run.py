#!/usr/bin/env python3
"""Times building an n-entry map with map:merge of n one-entry maps, followed by map:size, on each version of
versions.csv, and measures the memory of the built map (retained mode); see benchkit/benchkit.py for the
options.

Usage: python3 run.py --mode jvm|retained [--versions layered,compacted-initial,compacted,trie] [--ns 1000,2000] [--processes 3] [--run-dir NEW_DIRECTORY]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "benchkit"))
import benchkit

# Retained mode runs queries/map.xq.template, which returns the map itself; QueryBench reports its size.
BENCHMARK = benchkit.Benchmark(query="queries/size.xq.template", expected=str,
                               default_ns="1000,4000,16000,64000,256000,512000",
                               retained_query="queries/map.xq.template")

if __name__ == "__main__":
    benchkit.main(BENCHMARK, HERE)
