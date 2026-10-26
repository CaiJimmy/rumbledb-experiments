# Experiments for "Improving language support in RumbleDB"

| Folder                     | What it measures                                                                                                           |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `function-call-benchmark/` | The cost of a function call before and after runtime plans, with a recursive Fibonacci                                     |
| `function-loop-benchmark/` | The same, but with every call at one call site in a loop, where `once` can reuse its copy                                  |
| `map-benchmark/`           | Time and memory of building a map with `map:put`: without compaction, with compaction (#1771), and with hash tries (#1975) |
| `map-date-key-benchmark/`  | The same with `xs:date` keys, before and after the hashing fix of #1978                                                    |
| `map-merge-benchmark/`     | Whether hash tries make building a map in one `map:merge` slower                                                           |
| `map-lookup-benchmark/`    | Whether hash tries make `map:get` slower                                                                                   |
| `lsp-benchmark/`           | Correctness and response times of the JSONiq language server; see its own [README](lsp-benchmark/README.md)                |
| `benchkit/`                | The runner and analysis code that all benchmarks share                                                                     |

The map benchmarks use five RumbleDB commits; [map-versions.md](map-versions.md) lists them and says which
benchmark compares which.

## Where the thesis numbers come from

Only the runs that the thesis reports are kept here, plus a few older logs that it cites. Every run directory
has a `manifest.json` (the command, the commits, the jar hashes and the machine), the measurements in
`raw.csv`, a copy of the code that ran, and the console output of every JVM. Next to the raw data,
`summary.txt` holds the tables that `analyze.py` prints for that run, and `summary.csv` the same medians in
one row per version and n, ready for plotting.

| Thesis                           | Data                                                                                                                                                                                                         |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Fibonacci: median time           | `function-call-benchmark/data/jvm/run-2026-10-22T012629Z-11017/` (`main/`, and `large-copy/` for `copy` at n = 28 and 30)                                                                                    |
| Fibonacci: largest heap          | `function-call-benchmark/data/memory/heap/run-2026-10-22T063139Z-14564/`; out of memory: `function-call-benchmark/data/logs/`; full collections with `jcmd`: `function-call-benchmark/data/memory/once-n26/` |
| Loop: time and allocation        | `function-loop-benchmark/data/jvm/run-2026-10-22T054827Z-12935/`; stack overflow of `copy`: `function-loop-benchmark/data/logs/`                                                                             |
| Maps: time and allocation        | `map-benchmark/data/jvm/run-2026-10-21T230158Z-1057/`                                                                                                                                                        |
| Maps: memory of the finished map | `map-benchmark/data/retained/run-2026-10-22T001851Z-3064/`                                                                                                                                                   |
| `map:merge`                      | `map-merge-benchmark/data/jvm/run-2026-10-23T105657Z-52402/`, `map-merge-benchmark/data/retained/run-2026-10-23T105748Z-52402/`                                                                              |
| `map:get`                        | `map-lookup-benchmark/data/jvm/run-2026-10-23T112356.184295Z-2f1c3c68/` (insertion order), `map-lookup-benchmark/data/jvm/run-2026-10-23T113629.205349Z-5ad7a5ca/` (keys 7,919 apart)                        |

A few things to keep in mind when comparing with the thesis:

- The thesis calls the function-call versions `copy`, `snapshot` and `plan`. Here they are `copy`, `once`
  and `final`. There is also `plans`, the first commit with runtime plans, which was measured but is not in
  the thesis.
- Each version and n runs in three JVMs. The thesis reports the median of the three per-JVM medians (what
  `analyze.py` prints), and when it says how much the results vary, it means the spread between those three.
- Memory is in decimal MB (10^6 bytes) everywhere except in the GC logs and the output of
  `memory/heap.py`, which use MiB.

## What you need

- JDK 17, with `JAVA_HOME` pointing to it. `spark-submit` uses the JVM of `JAVA_HOME`, and Homebrew's
  `spark-submit` falls back to Java 21 if it is not set.
- Spark 4 with `spark-submit` on the `PATH`. The results were measured with Spark 4.2.0 in local mode.
- Python 3.9 or later. No packages are needed.
- Maven and a RumbleDB checkout, to build the jars. The build scripts look for it in `../rumble` by default,
  or take its path as an argument.

All results come from an Apple M3 MacBook Air (Mac15,13, no fan, 24 GB) with Java 17 (Eclipse Temurin) and
Spark 4.2.0. Each run also records its environment in `manifest.json`, and the `setup` rows of `raw.csv` show
the Java and Spark versions of the JVM that did the measuring. On macOS the scripts keep the machine awake
with `caffeinate`.

## How a benchmark folder is organized

```
versions.csv         the RumbleDB commits to compare: name,commit,description
queries/             the query; {n} is replaced by the parameter n
run.py               runs the benchmark (options and CSV format: ../benchkit/README.md)
analyze.py           prints the medians of one or more runs
build.sh             builds jars/<name>.jar for every version in versions.csv
run-all-jvm.sh       the timed run: the query alone, timed inside the JVM, with the bytes it allocates
run-all-retained.sh  the memory run: how much memory the result of the query (a map) takes
data/jvm/            timed runs, each in run-<UTC time>-<id>/; scripts that run several
                     invocations group them in one run-<UTC time>-<pid>/
data/retained/       memory runs
data/logs/           logs of failed JVMs from older runs that the thesis cites (Fibonacci, loop)
```

The jars (about 80 MB each) and `build/` are not in the repository; `build.sh` rebuilds them from the
commits in `versions.csv`. The loop benchmark uses the jars of the Fibonacci benchmark, and the other map
benchmarks use those of `map-benchmark`, through symbolic links.

## Running

To rerun one benchmark, for example the maps:

```sh
cd map-benchmark
./build.sh ../../rumble   # path to the RumbleDB checkout
./run-all-jvm.sh
python3 analyze.py
```

`./run-overnight.sh` runs everything in the thesis back to back once the jars are built, which takes about
9 hours: the map, date-key and `map:merge` benchmarks in both modes, the lookup benchmark, the Fibonacci
benchmark with its heap runs (`function-call-benchmark/memory/run-heap.sh`), and the loop benchmark.

A new run always goes into a new directory and never touches existing results. Use
`--run-dir NEW_DIRECTORY` to pick the directory yourself. [benchkit/README.md](benchkit/README.md) describes
the manifest, the CSV columns and the analysis.

## License

Copyright 2026 Jimmy Cai. The code is licensed under the [Apache License, Version 2.0](LICENSE).
