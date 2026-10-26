"""Writes a run directory: manifest.json (what was run, and on which machine), sources/ (a copy of the query
and of the code that ran it), raw.csv (one row per measurement) and logs/ (the output of every JVM).
"""
import csv
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

KIT = Path(__file__).resolve().parent
FIELDS = ["timestamp", "mode", "version", "commit", "n", "query", "work", "process", "phase", "iteration",
          "seconds", "status", "result", "allocated_bytes", "retained_bytes"]


def versions(experiment):
    with open(experiment / "versions.csv") as f:
        return {row["name"]: row["commit"] for row in csv.DictReader(f)}


def command_output(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return (p.stdout + p.stderr).strip()
    except Exception as e:  # a missing tool should not stop the benchmark
        return f"unavailable: {e}"


def environment():
    return {
        "date": datetime.date.today().isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": command_output(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "memory_bytes": command_output(["sysctl", "-n", "hw.memsize"]),
        # spark-submit runs the JVM of JAVA_HOME; the JVM that ran is also in the setup rows of the CSV file.
        "java_home": os.environ.get("JAVA_HOME", "not set"),
        "java": command_output(["java", "-version"]).splitlines()[:2],
        "spark_submit": spark_version(),
    }


def spark_version():
    """The version of spark-submit, from the line "... version 4.2.0" of the banner of --version."""
    match = re.search(r"version (\S+)", command_output(["spark-submit", "--version"]))
    return match.group(1) if match else "unavailable"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_run(benchmark, experiment, args):
    """Creates the run directory, which must not exist yet, with the manifest, the sources and an empty
    raw.csv. Returns the manifest."""
    args.run_dir.parent.mkdir(parents=True, exist_ok=True)
    args.run_dir.mkdir()
    sources = args.run_dir / "sources"
    sources.mkdir()
    (args.run_dir / "logs").mkdir()
    query = benchmark.retained_query if args.mode == "retained" else benchmark.query
    inputs = {
        "query.template": experiment / query,
        "run.py": experiment / "run.py",
        "versions.csv": experiment / "versions.csv",
    }
    for name in ("benchkit.py", "runner.py", "recording.py", "analysis.py", "QueryBench.java"):
        inputs[name] = KIT / name
    for name, source in inputs.items():
        shutil.copyfile(source, sources / name)
    commits = versions(sources)
    manifest = {
        "schema_version": 1,
        "run_id": uuid.uuid4().hex,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "experiment": experiment.name,
        "command": sys.argv,
        "working_directory": str(Path.cwd()),
        "options": {key: value for key, value in vars(args).items() if key != "run_dir"},
        "query": query,
        "versions": {name: commits[name] for name in args.versions},
        "jar_sha256": {name: sha256(experiment / "jars" / f"{name}.jar") for name in args.versions},
        "harness_sha256": sha256(KIT / "target" / "querybench.jar"),
        "source_sha256": {name: sha256(sources / name) for name in inputs},
        "environment": environment(),
    }
    with (args.run_dir / "manifest.json").open("x") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    with (args.run_dir / "raw.csv").open("x", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    return manifest


def record(run_dir, metadata, rows, output):
    """Appends the rows of one JVM to raw.csv, and saves its output in logs/. metadata has the columns
    that are the same for all rows of the JVM: mode, version, commit, n, process and work."""
    with (run_dir / "raw.csv").open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        for row in rows:
            writer.writerow(dict(row, **metadata, query="main",
                                 timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
                                 seconds=f"{row['seconds']:.6f}"))
    log = run_dir / "logs" / f"{metadata['version']}-n{metadata['n']}-process{metadata['process']}.log"
    with log.open("x") as f:
        f.write(output)
