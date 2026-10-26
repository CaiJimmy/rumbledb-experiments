#!/usr/bin/env python3
"""Prints, for every run in data/memory/heap/ (from memory/run-heap.sh), the largest heap after a garbage
collection, which is about the most memory that the run kept alive at once, and the result of the run.

Usage: python3 memory/heap.py [--save] [folder]   (default: the latest heap run)
--save also writes the table to summary.txt and summary.csv in the folder.
"""
import contextlib
import csv
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
# A G1 log line such as "[0.063s] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 23M->21M(400M) 1.390ms".
PAUSE = re.compile(r"\] GC\(\d+\) Pause .* (\d+)M->(\d+)M\((\d+)M\)")


def peak_after_gc(gc_log):
    if not gc_log.is_file():
        return None
    return max((int(m.group(2)) for m in map(PAUSE.search, gc_log.read_text().splitlines()) if m), default=None)


def format_run(heap, result):
    measurement = f"{heap:,}" if heap is not None else "no GC sample"
    return f"{measurement} ({result})"


def main():
    args = sys.argv[1:]
    save = "--save" in args
    args = [a for a in args if a != "--save"]
    folder = Path(args[0]) if args else HERE / "data" / "memory" / "heap"
    if not args:
        latest = sorted(folder.glob("run-*"))
        if latest:
            folder = latest[-1]
    runs = {}
    commits = {}
    for run in folder.iterdir():
        if not run.is_dir() or not re.fullmatch(r".+-n[0-9]+", run.name):
            continue
        version, n = run.name.rsplit("-n", 1)
        # stdout.txt has the result of the query, and then the line "exit code: <code>" from run.py.
        stdout = (run / "stdout.txt").read_text().split()
        result = stdout[0] if stdout and stdout[-3:] == ["exit", "code:", "0"] else "failed"
        runs[version, int(n)] = (peak_after_gc(run / "gc.log"), result)
        if (run / "manifest.json").is_file():
            commits[version] = json.loads((run / "manifest.json").read_text())["commit"]
    with (HERE / "versions.csv").open() as source:
        configured = [row["name"] for row in csv.DictReader(source)]
    present = {version for version, n in runs}
    versions = [v for v in configured if v in present] + sorted(present - set(configured))
    text = io.StringIO()
    with contextlib.redirect_stdout(text):
        print("largest heap after GC, in MiB (result of the run)")
        print(f"{'n':>4}" + "".join(f"{v:>22}" for v in versions))
        for n in sorted({k[1] for k in runs}):
            cells = [format_run(*runs[v, n]) if (v, n) in runs else "-" for v in versions]
            print(f"{n:>4}" + "".join(f"{c:>22}" for c in cells))
    print(text.getvalue(), end="")
    if save:
        (folder / "summary.txt").write_text(text.getvalue())
        with (folder / "summary.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["version", "commit", "n", "peak_heap_after_gc_mib", "result"])
            for version, n in sorted(runs, key=lambda k: (versions.index(k[0]), k[1])):
                heap, result = runs[version, n]
                writer.writerow([version, commits.get(version, ""), n, "" if heap is None else heap, result])
        print(f"Saved {folder / 'summary.txt'} and summary.csv")


if __name__ == "__main__":
    main()
