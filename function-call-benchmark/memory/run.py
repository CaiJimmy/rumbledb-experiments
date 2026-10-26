#!/usr/bin/env python3
"""Runs local:fib(n) once with spark-submit and a GC log, and every INTERVAL seconds saves a histogram of the
live objects of the JVM (jcmd GC.class_histogram, which runs a full garbage collection first)."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from run import fib
import recording


def execute(command, out, timeout, interval):
    """Runs command with its output in out/stdout.txt and out/stderr.txt. Returns its exit code, or 124 if
    it is still running after timeout seconds. With an interval greater than 0, saves a histogram every
    interval seconds in out/histo-<seconds>s.txt."""
    with (out / "stdout.txt").open("w") as stdout, (out / "stderr.txt").open("w") as stderr:
        # A new session, so that the JVM that spark-submit starts can be found and killed with it.
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        start = time.monotonic()
        try:
            while True:
                left = timeout - (time.monotonic() - start)
                if left <= 0:
                    stderr.write(f"\nTimed out after {timeout} seconds\n")
                    return 124
                try:
                    return process.wait(timeout=min(interval, left) if interval else left)
                except subprocess.TimeoutExpired:
                    pass
                if interval and time.monotonic() - start < timeout:
                    save_histograms(process, out, stderr, int(time.monotonic() - start))
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def save_histograms(process, out, stderr, seconds):
    jvms = subprocess.run(["pgrep", "-g", str(process.pid), "-f", "SparkSubmit"], capture_output=True, text=True)
    for pid in jvms.stdout.split():
        with (out / f"histo-{seconds}s.txt").open("w") as histogram:
            subprocess.run(["jcmd", pid, "GC.class_histogram"], stdout=histogram, stderr=stderr, timeout=600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", choices=recording.versions(HERE))
    parser.add_argument("n", type=int)
    parser.add_argument("interval", type=float, nargs="?", default=15)
    parser.add_argument("memory", nargs="?", default="12g")
    parser.add_argument("--timeout", type=float, default=3600)
    args = parser.parse_args()
    jar = HERE / "jars" / f"{args.version}.jar"
    if not jar.is_file():
        parser.error(f"Missing jar: {jar}")
    out = Path(os.environ.get("MEMORY_OUT", HERE / "data/memory")) / f"{args.version}-n{args.n}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()  # fails if this version and n were already measured in this folder
    out = out.resolve()
    template = (HERE / "queries/fib.jq.template").read_text()
    query = out / "query.jq"
    query.write_text(template.replace("{n}", str(args.n)))
    command = ["spark-submit", "--driver-memory", args.memory, "--conf", "spark.ui.showConsoleProgress=false",
               "--driver-java-options", f"-Xlog:gc:file={out / 'gc.log'}:uptime", str(jar), "run", str(query)]
    manifest = dict(version=args.version, commit=recording.versions(HERE)[args.version],
                    jar_sha256=recording.sha256(jar), query_sha256=recording.sha256(query),
                    options=vars(args), command=command, environment=recording.environment())
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if sys.platform == "darwin":
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
    status = execute(command, out, args.timeout, args.interval)
    result = (out / "stdout.txt").read_text().strip()
    if status == 0 and result != str(fib(args.n)):
        status = 1
        with (out / "stderr.txt").open("a") as log:
            log.write(f"\nIncorrect Fibonacci result: expected {fib(args.n)}, got {result!r}\n")
    with (out / "stdout.txt").open("a") as log:
        log.write(f"\nexit code: {status}\n")
    print(f"{args.version} n={args.n}: exit code {status}; output: {out}")
    return status


if __name__ == "__main__":
    sys.exit(main())
