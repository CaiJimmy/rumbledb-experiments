# benchkit: comparing RumbleDB versions on a query

This is the code that all the benchmarks share. A benchmark runs one query, with a parameter n, on several
RumbleDB commits, and reports the median time for each version and n.

| File               | What it does |
|--------------------|--------------|
| `benchkit.py`      | `Benchmark`, the command-line options, and `main` and `analyze_main`, which `run.py` and `analyze.py` call |
| `runner.py`        | runs the queries and checks their results |
| `recording.py`     | writes the run directory |
| `analysis.py`      | reads runs and prints the medians |
| `QueryBench.java`  | runs and times a query inside one JVM; compiled automatically into `target/` |
| `build.sh`         | builds one RumbleDB jar per commit in a benchmark's `versions.csv` |

You need JDK 17 (`java`, `javac`, `jar`) with `JAVA_HOME` set to it, Spark 4 with `spark-submit` on the
`PATH`, Python 3.9 or later, and Maven to build the jars.

## How a query is measured

Each JVM is its own `spark-submit` process, with Spark in local mode. Inside it, `QueryBench` creates the
Spark session and a `Rumble` instance once. It then runs the query `--warmups` times without timing it, and
`--iterations` times with `System.nanoTime()` around `Rumble.runQueryToString`, which covers parsing,
compiling, evaluating and serializing. Before each iteration it calls `System.gc()`. It also records how many
bytes the thread evaluating the query allocates (`com.sun.management.ThreadMXBean`), which is the garbage the
query creates. All benchmarks here evaluate their query on that thread.

`--mode` picks what is measured:

- **`jvm`**: the time and the allocated bytes, as described above.
- **`retained`**: the memory of the result. This runs the benchmark's `retained_query`, which returns a single
  item (a map). `QueryBench` keeps the item alive and reports the heap used after a full GC minus the heap
  used after a full GC before the query. The result it checks is the item's `getSize()`.

The session comes from RumbleDB's own `SparkSessionManager`, with the same Spark configuration as RumbleDB's
command line, and the RumbleDB jar is the application jar of `spark-submit`, just as when RumbleDB runs from
the command line. `QueryBench` is passed with `--jars`, so Spark loads it with the same class loader as
RumbleDB.

`QueryBench` is compiled once, against the jar of the first version in a run, and works with every version,
since the RumbleDB methods it calls have the same signatures in all of them. Two calls go through reflection:
`SparkSessionManager` moved from `sparksoniq.spark` to `org.rumbledb.spark` in August 2026, and the
`Rumble` constructor takes a `SparkSession`, which would otherwise need Spark on the class path of `javac`.

## Order of the runs

`--processes` is the number of JVMs per version and n (3 by default). The
runner runs every version and n once, which makes a round, before starting the next round, and each round
starts with a different version (round 0: v1, v2, v3; round 1: v2, v3, v1; and so on). That way a slow drift
of the machine, such as heating up, affects all versions alike. `--max-n version=n` skips larger n for a
version, and a version that times out is not run for larger n either. On macOS, `caffeinate` keeps the
machine awake while it runs.

## Output

Each invocation creates a new directory, `data/<mode>/run-<UTC time>-<id>/`, or the one given with
`--run-dir`, which must not exist yet. The `run-all-*.sh` scripts put their invocations together in one
directory, for example `main/` and `large-copy/` for the Fibonacci benchmark.

```text
run-2026-10-22T012629Z-11017/
  summary.txt            the output of analyze.py for the whole directory (main/ and large-copy/ together)
  summary.csv            the same medians, one row per mode, metric, version and n
run-2026-10-22T012629Z-11017/main/
  manifest.json          the command, the options, the commits and SHA-256 of the jars, the SHA-256 of the
                         files in sources/, and the machine, Java and Spark versions
  raw.csv                one row per measurement
  sources/               a copy of the query template, run.py, versions.csv and the benchkit code that ran
  logs/                  the output of every JVM, such as final-n26-process0.log
```

The jars are not copied. To check them, rebuild them from the commits in `versions.csv` and compare their
SHA-256 with the manifest.

`raw.csv` has these columns:

| Column      | Meaning |
|-------------|---------|
| `timestamp` | when the row was written |
| `mode`      | `jvm` or `retained` |
| `version`, `commit` | the name in `versions.csv` and its commit |
| `n`, `work` | the parameter, and the units of work for that n if the benchmark defines them (function calls) |
| `query`     | always `main` |
| `process`   | which JVM, from 0 to `--processes` − 1 |
| `phase`     | `setup` (creating the session and the `Rumble` instance; its `result` holds the Java and Spark versions and the maximum heap), `warmup`, `measure`, or `process` (how a failed JVM ended) |
| `iteration` | the iteration within the phase |
| `seconds`   | the time |
| `status`    | `ok`, `wrong` (unexpected result), `error`, `timeout`, `incomplete` or `invalid-output` |
| `result`    | the serialized result, which is checked against the expected value. RumbleDB writes an XML declaration in front of XQuery results since #1863; it is ignored. |
| `allocated_bytes` | the bytes allocated by the query (jvm mode) |
| `retained_bytes`  | the memory of the result (retained mode) |

If a JVM fails, the rows of the iterations it finished are kept and its log is saved. The runner carries on
with the other JVMs, but exits with an error at the end.

## Analysis

Run `python3 analyze.py` in a benchmark folder. For every version and n, it prints the median over the JVMs of
each JVM's median, the number of JVMs, and the spread between them, (max − min) / median. Then it prints the
cost per unit of work at the largest n, and tables of the allocated and retained memory in MB (10^6 bytes).
Without arguments it reads the latest run in `data/jvm/` and in `data/retained/`. You can also pass run
directories, directories of runs, or CSV files; several runs given together are pooled.

`python3 analyze.py --save RUN_DIRECTORY ...` analyzes each directory on its own and saves the output in its
`summary.txt`, and the medians in its `summary.csv`. The `run-all-*.sh` scripts do this at the end of a run.
`summary.csv` has the columns:

| Column      | Meaning |
|-------------|---------|
| `mode`, `metric` | `jvm` or `retained`, and `seconds`, `allocated_bytes` or `retained_bytes` |
| `version`, `commit`, `n`, `work` | as in `raw.csv` |
| `jvms`      | the number of JVMs with a measurement |
| `median`, `min`, `max` | the median, smallest and largest of the per-JVM medians, in seconds or bytes |
| `spread`    | (max − min) / median |
| `failed_rows` | the rows that did not end with status `ok` (0 for every run kept here) |

A retained-mode run also records the time of its query, which appears as `seconds` rows; `analyze.py` does
not print it.

## Adding a benchmark

```text
my-benchmark/
  versions.csv            name,commit,description
  queries/q.xq.template   the query; {n} is replaced by the value of n
  run.py                  defines BENCHMARK and calls benchkit.main
  analyze.py              calls benchkit.analyze_main
  build.sh                calls ../benchkit/build.sh
```

```python
# run.py
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "benchkit"))
import benchkit

BENCHMARK = benchkit.Benchmark(query="queries/q.xq.template", expected=lambda n: str(n), default_ns="1,1000,2000")
if __name__ == "__main__":
    benchkit.main(BENCHMARK, HERE)
```

Then run `./build.sh ../path/to/rumble`, `python3 run.py --mode jvm` and `python3 analyze.py`.
