#!/usr/bin/env python3
"""Summarizes the runs of memory/run.sh in data/memory/<version>-n<n>/: for every jcmd histogram, the heap
after the young GC just before it, the heap after the full GC that jcmd runs first, the bytes of the live
objects in the histogram, and the number of RuntimeStaticContext objects; and the heap after the last GC.

Usage: python3 memory/histograms.py [--save] [folder ...]   (default: every such folder in data/memory/)
--save also writes the table to summary.txt and summary.csv in each folder.
"""
import contextlib
import csv
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PAUSE = re.compile(r"\] GC\(\d+\) Pause (Young|Full) \((.*?)\).* (\d+)M->(\d+)M\((\d+)M\)")
FIELDS = ["seconds", "young_gc_after_mib", "full_gc_after_mib", "live_bytes", "runtime_static_contexts"]


def summarize(folder):
    """The rows of FIELDS, one per histogram, the heap after the last GC in MiB, and the exit code."""
    young, full, last = None, [], None
    for line in (folder / "gc.log").read_text().splitlines():
        m = PAUSE.search(line)
        if not m:
            continue
        last = int(m.group(4))
        if m.group(1) == "Young":
            young = last
        elif m.group(2) == "Heap Inspection Initiated GC":
            # jcmd GC.class_histogram runs this full GC; the young GC just before it is the last one seen.
            full.append((young, last))
    histograms = sorted(folder.glob("histo-*s.txt"), key=lambda p: int(p.stem[len("histo-"):-1]))
    rows = []
    for (young_after, full_after), histogram in zip(full, histograms):
        text = histogram.read_text()
        live = int(re.search(r"^Total\s+\d+\s+(\d+)", text, re.M).group(1))
        contexts = re.search(r"^\s*\d+:\s+(\d+)\s+\d+\s+org\.rumbledb\.context\.RuntimeStaticContext\b", text, re.M)
        rows.append(dict(seconds=int(histogram.stem[len("histo-"):-1]), young_gc_after_mib=young_after,
                         full_gc_after_mib=full_after, live_bytes=live,
                         runtime_static_contexts=int(contexts.group(1)) if contexts else 0))
    exit_code = re.search(r"exit code: (\d+)", (folder / "stdout.txt").read_text())
    return rows, last, exit_code.group(1) if exit_code else "unknown"


def main():
    args = sys.argv[1:]
    save = "--save" in args
    folders = [Path(a) for a in args if a != "--save"] or sorted(
        p for p in (HERE / "data" / "memory").iterdir() if p.is_dir() and re.fullmatch(r".+-n[0-9]+", p.name))
    for folder in folders:
        rows, last, exit_code = summarize(folder)
        text = io.StringIO()
        with contextlib.redirect_stdout(text):
            print(f"{folder.name}: exit code {exit_code}, heap after the last GC {last:,} MiB")
            print(f"{'histogram':>9} {'after young GC':>15} {'after full GC':>14} {'live bytes':>15} "
                  f"{'RuntimeStaticContext':>21}")
            for r in rows:
                print(f"{str(r['seconds']) + ' s':>9} {r['young_gc_after_mib']:>11,} MiB {r['full_gc_after_mib']:>10,} MiB "
                      f"{r['live_bytes']:>15,} {r['runtime_static_contexts']:>21,}")
        print(text.getvalue())
        if save:
            (folder / "summary.txt").write_text(text.getvalue())
            with (folder / "summary.csv").open("w", newline="") as f:
                writer = csv.DictWriter(f, FIELDS)
                writer.writeheader()
                writer.writerows(rows)


if __name__ == "__main__":
    main()
