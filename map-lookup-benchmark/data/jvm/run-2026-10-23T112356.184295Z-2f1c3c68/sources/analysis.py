"""Locate run measurements and summarize timing, allocation and retained memory.

The current run-directory format is the main input. Standalone CSVs use the same analysis; a few defaults
also allow the historical process-mode CSVs to be read without a separate migration layer.
"""
import csv
import statistics
from collections import defaultdict

from recording import DEFAULT_QUERY, versions


def measurement_paths(inputs):
    """Accept CSV files, individual run directories, or wrapper directories containing several runs."""
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
    """Select the latest dated output per mode, including historical raw-<date>.csv files."""
    inputs = []
    for mode in ("jvm", "retained"):
        folder = experiment / "data" / mode
        candidates = list(folder.glob("raw-*.csv")) + [p for p in folder.glob("run-*") if p.is_dir()]
        if candidates:
            inputs.append(max(candidates, key=lambda p: p.name.split("-", 1)[1]))
    return inputs


def load(paths, column="seconds"):
    """Reads raw CSV files into values[(mode, query, version, n)] = [per-process medians of successful measurements]
    and failed[(mode, query, version, n)] = number of failed processes or measurements. Measurements without
    a value in the column, such as the rows of other modes or of older files, are left out."""
    times, failed = defaultdict(list), defaultdict(int)
    processes = defaultdict(list)
    commits = {}
    for path in paths:
        with open(path) as f:
            for index, row in enumerate(csv.DictReader(f)):
                version, commit = row["version"], row.get("commit", "")
                if commit:
                    if version in commits and commits[version] != commit:
                        raise ValueError(f"Conflicting commits for {version}: {commits[version]} and {commit}")
                    commits[version] = commit
                # Rows written before benchkit have no mode, query or phase: they are process runs.
                mode, phase = row.get("mode") or "process", row.get("phase") or "process"
                if phase not in ("process", "measure"):
                    continue
                key = (mode, row.get("query") or DEFAULT_QUERY, row["version"], int(row["n"]))
                if row["status"] == "ok":
                    if row.get(column):
                        # JVM iterations share a process; each independent process gets one median.
                        process = row.get("process") if phase == "measure" else None
                        identity = process if process is not None else f"row-{index}"
                        processes[path, key, identity].append(float(row[column]))
                else:
                    failed[key] += 1
    for (_, key, _), measurements in processes.items():
        times[key].append(statistics.median(measurements))
    return times, failed


def analyze(benchmark, experiment, paths):
    """Prints the median and spread across processes, and the cost per unit of work.

    In process mode, the median of n = 1 of the same version is subtracted as start-up; in jvm mode, the times contain the query alone. The medians of the allocated
    bytes (jvm mode) and of the retained bytes (retained mode) follow in their own tables."""
    print("Runtime of the measured JVMs:", ", ".join(sorted(runtimes(paths))) or "not recorded")
    times, failed = load(paths)
    for mode, query in sorted({(m, q) for m, q, _, _ in times if m != "retained"}):
        startup = mode == "process"
        title = "seconds" + (", minus the median of n = 1 (start-up)" if startup else ", query only")
        print_table(benchmark, experiment, times, failed, mode, query, title, unit=1, suffix=" s",
                    subtract_startup=startup, show_cost=True)
    for column, title in (("allocated_bytes", "MB allocated"), ("retained_bytes", "MB retained")):
        values, _ = load(paths, column)
        for mode, query in sorted({(m, q) for m, q, _, _ in values}):
            print_table(benchmark, experiment, values, failed, mode, query, title, unit=1e6, suffix=" MB",
                        subtract_startup=False, show_cost=False)
    if failed:
        print("\nfailed (mode, query, version, n): count:", dict(failed))


def runtimes(paths):
    """The Java and Spark versions that QueryBench reported in the setup rows."""
    found = set()
    for path in paths:
        with open(path) as f:
            found |= {row["result"] for row in csv.DictReader(f) if row.get("phase") == "setup" and row["result"]}
    return found


def print_table(benchmark, experiment, values, failed, mode, query, title, unit, suffix, subtract_startup,
                show_cost):
    """One table of the medians of values (divided by unit) per version and n. With subtract_startup, the
    median of n = 1 of each version is subtracted; with show_cost, the cost per unit of work follows."""
    order = list(versions(experiment))
    group = {(v, n): t for (m, q, v, n), t in values.items() if (m, q) == (mode, query)}
    vs = sorted({v for v, _ in group}, key=lambda v: order.index(v) if v in order else 99)
    ns = sorted({n for _, n in group})
    median = {k: statistics.median(t) / unit for k, t in group.items()}
    startup = {v: median.get((v, 1), 0.0) if subtract_startup else 0.0 for v in vs}
    print(f"\n== {mode} mode" + (f", query {query}" if query != DEFAULT_QUERY else "") + f": median {title}"
          + "; (process count, spread = (max - min) / median)")
    work = benchmark.work
    print(f"{'n':>9}" + (f"{benchmark.work_name:>11}" if work else "") + "".join(f"{v:>28}" for v in vs))
    for n in ns:
        cells = []
        for v in vs:
            t = group.get((v, n))
            if not t:
                cell = "failed" if failed.get((mode, query, v, n)) else "-"
                cells.append(f"{cell:>28}")
                continue
            spread = (max(t) - min(t)) / unit / median[v, n] if median[v, n] else 0
            cells.append(f"{median[v, n] - startup[v]:12.4f}{suffix:<3}({len(t):>2}, {spread:4.0%})")
        print(f"{n:>9}" + (f"{work(n):>11,}" if work else "") + "".join(cells))
    if work and show_cost:
        print(f"Cost per {benchmark.work_name.rstrip('s')} at the largest n of each version:")
        for v in vs:
            n = max(n for (w, n) in median if w == v)
            units = work(n) - (work(1) if subtract_startup else 0)
            if units > 0:
                print(f"  {v:>8}: {(median[v, n] - startup[v]) / units * 1e6:10.3f} us at n = {n}")
