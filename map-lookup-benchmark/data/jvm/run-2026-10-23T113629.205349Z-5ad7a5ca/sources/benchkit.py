"""Public entry points for the function and map experiments.

Each experiment defines a Benchmark, calls main() to run it, and calls analyze_main() to summarize it.
This module owns command-line options; execution, recording and statistics live in their own modules.
"""
import argparse
import datetime
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import analysis
import recording
import runner


@dataclass
class Benchmark:
    query: str                                   # the query template, relative to the experiment directory
    expected: Callable[[int], str]               # the expected serialized result for n
    default_ns: str = "1"
    work: Optional[Callable[[int], int]] = None  # units of work for n, such as function calls
    work_name: str = "work"                      # what a unit of work is, in the output of analyze
    retained_query: Optional[str] = None         # the template of retained mode, which returns one item


def parse_arguments(benchmark, experiment):
    parser = argparse.ArgumentParser(description=f"Runs the benchmark in {experiment.name}.")
    parser.add_argument("--mode", choices=["process", "jvm", "retained"], required=True)
    parser.add_argument("--versions", default=",".join(recording.versions(experiment)))
    parser.add_argument("--ns", default=benchmark.default_ns)
    parser.add_argument("--max-n", default="", help="largest n of some versions, e.g. copy=26,once=26")
    parser.add_argument("--processes", type=int, default=5, help="processes per version and n")
    parser.add_argument("--warmups", type=int, default=2, help="untimed iterations per process (jvm mode)")
    parser.add_argument("--iterations", type=int, default=5, help="timed iterations per process (jvm mode)")
    parser.add_argument("--driver-memory", default="4g")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per process")
    parser.add_argument("--run-dir", type=Path, help="new output directory (default: data/<mode>/run-<UTC time>-<id>)")
    args = parser.parse_args()
    args.versions = args.versions.split(",")
    args.ns = [int(n) for n in args.ns.split(",")]
    args.max_n = {v: int(n) for v, n in (item.split("=") for item in args.max_n.split(",") if item)}
    if args.run_dir is None:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%S.%fZ")
        args.run_dir = experiment / "data" / args.mode / f"run-{stamp}-{uuid.uuid4().hex[:8]}"
    if args.run_dir.exists():
        parser.error(f"{args.run_dir} already exists; choose a new --run-dir")
    unknown = set(args.versions) - recording.versions(experiment).keys()
    if unknown:
        parser.error(f"unknown versions: {', '.join(sorted(unknown))}")
    if set(args.max_n) - set(args.versions):
        parser.error("max-n must refer to selected versions")
    if len(set(args.versions)) != len(args.versions) or len(set(args.ns)) != len(args.ns):
        parser.error("versions and ns must not contain duplicates")
    if args.processes < 1 or args.iterations < 1 or args.warmups < 0 or args.timeout < 1:
        parser.error("processes, iterations and timeout must be positive; warmups must be nonnegative")
    if args.mode == "retained" and not benchmark.retained_query:
        sys.exit(f"{experiment.name} has no retained_query for retained mode")
    return args


def main(benchmark, experiment):
    """Prepare an invocation, save its inputs, then execute its measurements."""
    args = parse_arguments(benchmark, experiment)
    for version in args.versions:
        if not (experiment / "jars" / f"{version}.jar").is_file():
            sys.exit(f"Missing jars/{version}.jar; build the selected versions first")
    harness = None
    if args.mode != "process":
        runner.build_harness(experiment / "jars" / f"{args.versions[0]}.jar")
        harness = runner.HARNESS_JAR
    if sys.platform == "darwin":
        # Keep the machine awake for this invocation.
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
    manifest = recording.create_run(benchmark, experiment, args, harness)
    print(f"Run directory: {args.run_dir.resolve()}", flush=True)
    if not runner.run_all(benchmark, experiment, args, manifest):
        sys.exit("Benchmark failed or incomplete; see the recorded rows and logs.")


def analyze_main(benchmark, experiment):
    """Analyze explicit run directories/CSVs, or the latest jvm and retained outputs."""
    inputs = [Path(p) for p in sys.argv[1:]] or analysis.latest_runs(experiment)
    try:
        paths = analysis.measurement_paths(inputs)
    except ValueError as error:
        sys.exit(str(error))
    try:
        analysis.analyze(benchmark, experiment, paths)
    except ValueError as error:
        sys.exit(str(error))
