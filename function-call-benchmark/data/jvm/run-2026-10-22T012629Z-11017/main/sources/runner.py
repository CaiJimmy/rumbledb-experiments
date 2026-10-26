"""Benchmark execution: JVM setup, subprocesses, scheduling and result checks.

Times and results come from spark-submit (process mode) or QueryBench (JVM modes). Recording is delegated
to recording.py after a process returns, outside the measured interval.
"""
import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import recording

KIT = Path(__file__).resolve().parent
HARNESS_SOURCE = KIT / "QueryBench.java"
HARNESS_JAR = KIT / "target" / "querybench.jar"


def build_harness(rumbledb_jar):
    """Compiles QueryBench into target/querybench.jar if it is missing or older than its source."""
    if HARNESS_JAR.exists() and HARNESS_JAR.stat().st_mtime >= HARNESS_SOURCE.stat().st_mtime:
        return
    classes = KIT / "target" / "classes"
    shutil.rmtree(classes, ignore_errors=True)
    classes.mkdir(parents=True)
    # The harness calls RumbleDB's API, which is the same in every benchmarked version, so any of the jars
    # works; Spark is called only through reflection and is not needed.
    subprocess.run(["javac", "--release", "17", "-cp", str(rumbledb_jar), "-d", str(classes),
                    str(HARNESS_SOURCE)], check=True)
    subprocess.run(["jar", "cf", str(HARNESS_JAR), "-C", str(classes), "."], check=True)


def spark_submit(args):
    return ["spark-submit", "--driver-memory", args.driver_memory, "--conf", "spark.ui.showConsoleProgress=false"]


def run_process(jar, query_file, args):
    """One RumbleDB command-line run; yields one row (phase "process")."""
    cmd = spark_submit(args) + [str(jar), "run", str(query_file)]
    start = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired as e:
        return [dict(phase="process", iteration=0, seconds=time.perf_counter() - start, status="timeout",
                     result="")], text(e.stdout), text(e.stderr)
    seconds = time.perf_counter() - start
    lines = p.stdout.strip().splitlines()
    status = "ok" if p.returncode == 0 else "error"
    return [dict(phase="process", iteration=0, seconds=seconds, status=status,
                 result=lines[-1] if lines else "")], p.stdout, p.stderr


def run_jvm(jar, query_file, args):
    """One JVM that runs the query args.warmups + args.iterations times; yields one row per phase. In
    retained mode, QueryBench measures the memory of the result instead of timing the serialized query."""
    # With --jars, Spark loads the harness with the same class loader as RumbleDB, so that it can call it.
    cmd = spark_submit(args) + ["--class", "benchkit.QueryBench", "--jars", str(HARNESS_JAR),
                                str(jar), str(query_file), str(args.warmups), str(args.iterations),
                                "retained" if args.mode == "retained" else "time"]
    start = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
        stdout, stderr, status = p.stdout, p.stderr, "ok" if p.returncode == 0 else "error"
    except subprocess.TimeoutExpired as e:
        stdout, stderr, status = text(e.stdout), text(e.stderr), "timeout"
    rows = []
    try:
        for line in stdout.splitlines():
            if line.startswith("BENCH "):
                row = json.loads(line[len("BENCH "):])
                if (not isinstance(row, dict) or
                        set(row) - {"phase", "iteration", "seconds", "result", "allocated_bytes", "retained_bytes"} or
                        row.get("phase") not in {"setup", "warmup", "measure"} or
                        type(row.get("iteration")) is not int or
                        not isinstance(row.get("result"), str) or
                        type(row.get("seconds")) not in (int, float) or
                        not math.isfinite(row["seconds"]) or row["seconds"] < 0):
                    raise ValueError("Invalid BENCH record")
                rows.append(dict(row, status="ok"))
        expected = [("setup", 0)] + [("warmup", i) for i in range(args.warmups)] + [
            ("measure", i) for i in range(args.iterations)]
        actual = [(row.get("phase"), row.get("iteration")) for row in rows]
        if status == "ok" and actual != expected:
            status = "incomplete"
    except (ValueError, TypeError):
        status = "invalid-output" if status == "ok" else status
    if status != "ok":
        # Keep completed iterations and the raw log, even when output is malformed or incomplete.
        rows.append(dict(phase="process", iteration=0, seconds=time.perf_counter() - start, status=status,
                         result=""))
    return rows, stdout, stderr


def text(output):
    return output.decode(errors="replace") if isinstance(output, bytes) else (output or "")


def run_all(benchmark, experiment, args, manifest):
    """Runs the query for every n and version args.processes times, each time in a new process. A round runs
    every n and version once before the next round starts, and each round starts with another version
    (round 0: v1, v2, v3; round 1: v2, v3, v1; ...), so that a slow drift of the machine, such as heating up,
    affects all versions alike."""
    query = manifest["query"]
    template = (args.run_dir / "sources" / "query.template").read_text()
    suffix = Path(query.removesuffix(".template")).suffix
    run = run_process if args.mode == "process" else run_jvm
    commits = manifest["versions"]
    successful = True
    timed_out = {}  # version -> smallest n that timed out; larger n are not run either
    for process in range(args.processes):
        shift = process % len(args.versions)
        order = args.versions[shift:] + args.versions[:shift]
        for n in args.ns:
            for version in order:
                if n > args.max_n.get(version, n) or n >= timed_out.get(version, n + 1):
                    continue
                rows, stdout, stderr = run_once(run, experiment / "jars" / f"{version}.jar",
                                                template.replace("{n}", str(n)), suffix, args)
                check_results(rows, benchmark.expected(n))
                if not rows or any(row["status"] != "ok" for row in rows):
                    successful = False
                metadata = dict(mode=args.mode, version=version, commit=commits[version], n=n,
                                process=process, work=benchmark.work(n) if benchmark.work else "")
                recording.record(args.run_dir, metadata, rows, stdout + "\n--- stderr ---\n" + stderr)
                for row in rows:
                    print(version, n, process, row["phase"], row["iteration"],
                          f"{row['seconds']:.3f}", row["status"], flush=True)
                if any(row["status"] == "timeout" for row in rows):
                    timed_out[version] = n

    return successful


def check_results(rows, expected):
    """Mark incorrect query results; preserve setup rows and subprocess failures."""
    for row in rows:
        if row["status"] == "ok" and row["phase"] != "setup" and result_value(row) != expected:
            row["status"] = "wrong"


def result_value(row):
    """The result of a row without an XML declaration: since #1863 (October 2026), RumbleDB serializes the
    results of XQuery queries as XML with a declaration, which older versions omit."""
    result = row["result"]
    if result.startswith("<?xml"):
        result = result[result.find("?>") + 2:].lstrip()
    return result


def run_once(run, jar, query, suffix, args):
    """Writes the query to a temporary file and runs it once with run (run_process or run_jvm)."""
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as q:
        q.write(query)
    try:
        return run(jar, Path(q.name), args)
    finally:
        Path(q.name).unlink(missing_ok=True)
