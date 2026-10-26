#!/usr/bin/env python3
"""Times local:fib(n) on each version of versions.csv; see benchkit/benchkit.py for the options.

Usage: python3 run.py --mode jvm [--versions copy,once,plans,final] [--ns 1,18,20] [--processes 3] [--run-dir NEW_DIRECTORY]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "benchkit"))
import benchkit


def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def calls(n):
    # local:fib(n) is called once, and calls itself for n - 1 and n - 2 whenever n > 1.
    return 2 * fib(n + 1) - 1


BENCHMARK = benchkit.Benchmark(query="queries/fib.jq.template", expected=lambda n: str(fib(n)),
                               default_ns="1,18,20,22,24,26,28,30", work=calls, work_name="calls")

if __name__ == "__main__":
    benchkit.main(BENCHMARK, HERE)
