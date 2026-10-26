"""Reads the raw.csv files of runs and prints the median time, allocated memory and retained memory per
version and n.
"""
import contextlib
import csv
import io
import statistics
from collections import defaultdict

from recording import versions

SUMMARY_FIELDS = ["mode", "metric", "version", "commit", "n", "work", "jvms", "median", "min", "max", "spread",
                  "failed_rows"]
METRICS = ("seconds", "allocated_bytes", "retained_bytes")


def measurement_paths(inputs):
    """The raw.csv files of the given paths, each of which is a CSV file, a run directory, or a directory of
    runs (such as the main/ and large-copy/ runs of run-all-jvm.sh)."""
    paths = []
    for path in inputs:
        if path.is_dir():
            is_run = any((path / name).exists() for name in ("raw.csv", "manifest.json", "sources"))
            runs = [path] if is_run else sorted(p for p in path.iterdir() if p.is_dir())
            if not runs:
                raise ValueError(f"No recorded runs in {path}")
            files = []
            for run in runs:
                if not (run / "manifest.json").is_file() or not (run / "raw.csv").is_file():
                    raise ValueError(f"Incomplete run directory: {run}; provide a CSV explicitly to inspect it")
                files.append(run / "raw.csv")
        else:
            if not path.is_file():
                raise ValueError(f"No such measurement file: {path}")
            files = [path]
        for file in files:
            if file.resolve() not in paths:
                paths.append(file.resolve())
    return paths


def latest_runs(experiment):
    """The latest run directory in data/jvm/ and in data/retained/."""
    inputs = []
    for mode in ("jvm", "retained"):
        runs = sorted(p for p in (experiment / "data" / mode).glob("run-*") if p.is_dir())
        if runs:
            inputs.append(runs[-1])
    return inputs


def load(paths, column="seconds"):
    """Reads raw.csv files into values[(mode, version, n)], the medians of the measurements of each JVM, and
    failed[(mode, version, n)], the number of failed rows. Taking one median per
    JVM first gives every JVM the same weight. Rows without a value in the column are left out."""
    times, failed = defaultdict(list), defaultdict(int)
    processes = defaultdict(list)
    commits = {}
    for path in paths:
        with open(path) as f:
            for row in csv.DictReader(f):
                version, commit = row["version"], row["commit"]
                if commits.setdefault(version, commit) != commit:
                    raise ValueError(f"Conflicting commits for {version}: {commits[version]} and {commit}")
                if row["phase"] not in ("process", "measure"):
                    continue
                key = (row["mode"], version, int(row["n"]))
                if row["status"] != "ok":
                    failed[key] += 1
                elif row[column]:
                    processes[path, key, row["process"]].append(float(row[column]))
    for (_, key, _), measurements in processes.items():
        times[key].append(statistics.median(measurements))
    return times, failed


def analyze(benchmark, experiment, paths):
    """Prints the median time over the JVMs and the spread between them, and the cost per unit of work, followed
    by tables of the allocated bytes (jvm mode) and retained bytes (retained mode)."""
    print("Runtime of the measured JVMs:", ", ".join(sorted(runtimes(paths))) or "not recorded")
    times, failed = load(paths)
    if any(m == "jvm" for m, _, _ in times):
        print_table(benchmark, experiment, times, failed, "jvm", "seconds, query only", unit=1, suffix=" s",
                    show_cost=True)
    for column, title in (("allocated_bytes", "MB allocated"), ("retained_bytes", "MB retained")):
        values, _ = load(paths, column)
        for mode in sorted({m for m, _, _ in values}):
            print_table(benchmark, experiment, values, failed, mode, title, unit=1e6, suffix=" MB",
                        show_cost=False)
    if failed:
        print("\nfailed (mode, version, n): count:", dict(failed))


def runtimes(paths):
    """The Java and Spark versions that QueryBench reported in the setup rows."""
    found = set()
    for path in paths:
        with open(path) as f:
            found |= {row["result"] for row in csv.DictReader(f) if row.get("phase") == "setup" and row["result"]}
    return found


def print_table(benchmark, experiment, values, failed, mode, title, unit, suffix, show_cost):
    """One table of the medians of values (divided by unit) per version and n. With show_cost, the cost per
    unit of work follows."""
    order = list(versions(experiment))
    group = {(v, n): t for (m, v, n), t in values.items() if m == mode}
    vs = sorted({v for v, _ in group}, key=lambda v: order.index(v) if v in order else len(order))
    ns = sorted({n for _, n in group})
    median = {k: statistics.median(t) / unit for k, t in group.items()}
    print(f"\n== {mode} mode: median {title}; (JVM count, spread = (max - min) / median)")
    work = benchmark.work
    print(f"{'n':>9}" + (f"{benchmark.work_name:>11}" if work else "") + "".join(f"{v:>28}" for v in vs))
    for n in ns:
        cells = []
        for v in vs:
            t = group.get((v, n))
            if not t:
                cell = "failed" if failed.get((mode, v, n)) else "-"
                cells.append(f"{cell:>28}")
                continue
            spread = (max(t) - min(t)) / unit / median[v, n] if median[v, n] else 0
            cells.append(f"{median[v, n]:12.4f}{suffix:<3}({len(t):>2}, {spread:4.0%})")
        print(f"{n:>9}" + (f"{work(n):>11,}" if work else "") + "".join(cells))
    if work and show_cost:
        print(f"Cost per {benchmark.work_name.rstrip('s')} at the largest n of each version:")
        for v in vs:
            n = max(n for (w, n) in median if w == v)
            if work(n) > 0:
                print(f"  {v:>8}: {median[v, n] / work(n) * 1e6:10.3f} us at n = {n}")


def write_summary(benchmark, experiment, paths, directory):
    """Writes what analyze prints to directory/summary.txt, and the same medians to directory/summary.csv: one
    row per mode, metric, version and n, in seconds or bytes, where min and max are those of the per-JVM
    medians and failed_rows counts the rows that did not end with status ok."""
    text = io.StringIO()
    with contextlib.redirect_stdout(text):
        analyze(benchmark, experiment, paths)
    (directory / "summary.txt").write_text(text.getvalue())
    print(text.getvalue(), end="")
    order = list(versions(experiment))
    commits = {}
    for path in paths:
        with open(path) as f:
            commits.update((row["version"], row["commit"]) for row in csv.DictReader(f))
    rows = []
    for metric in METRICS:
        values, failed = load(paths, metric)
        keys = set(values) | (set(failed) if metric == "seconds" else set())
        for mode, version, n in keys:
            jvm_medians = values.get((mode, version, n), [])
            if metric != "seconds" and not jvm_medians:
                continue
            row = dict(mode=mode, metric=metric, version=version, commit=commits[version], n=n,
                       work=benchmark.work(n) if benchmark.work else "", jvms=len(jvm_medians),
                       failed_rows=failed.get((mode, version, n), 0))
            if jvm_medians:
                median = statistics.median(jvm_medians)
                number = (lambda x: round(x, 6)) if metric == "seconds" else round
                row.update(median=number(median), min=number(min(jvm_medians)), max=number(max(jvm_medians)),
                           spread=round((max(jvm_medians) - min(jvm_medians)) / median, 4) if median else 0)
            rows.append(row)
    rows.sort(key=lambda r: (r["mode"], METRICS.index(r["metric"]),
                             order.index(r["version"]) if r["version"] in order else len(order), r["n"]))
    with (directory / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
