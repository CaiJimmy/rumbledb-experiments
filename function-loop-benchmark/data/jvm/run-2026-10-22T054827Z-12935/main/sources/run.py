#!/usr/bin/env python3
"""Times n calls of a function at one call site, in a loop, on each version of versions.csv; see
benchkit/benchkit.py for the options.

Usage: python3 run.py --mode process|jvm [--versions copy,once,plans,final] [--ns 10000,100000]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "benchkit"))
import benchkit

# sum(2i + 1 for i = 1..n) = n(n + 1) + n; the loop makes n calls of local:f.
BENCHMARK = benchkit.Benchmark(query="queries/loop.jq.template", expected=lambda n: str(n * (n + 1) + n),
                               default_ns="10000,30000,100000,300000,1000000", work=lambda n: n,
                               work_name="calls")

if __name__ == "__main__":
    benchkit.main(BENCHMARK, HERE)
