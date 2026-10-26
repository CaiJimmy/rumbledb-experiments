# Function calls: recursive Fibonacci

How much does a function call cost in RumbleDB, before and after runtime plans? This is the benchmark of the
section "Function calls in RumbleDB" in the Evaluation chapter of the thesis (`<sec:eval-function-calls>`).

## Query

`queries/fib.jq.template`, where `run.py` fills in `{n}`:

```jsoniq
declare function local:fib($n as integer) as integer {
  if ($n le 1) then $n else local:fib($n - 1) + local:fib($n - 2)
};
local:fib({n})
```

F(n) takes 2 F(n+1) − 1 calls. The cost per call is the time of the whole query divided by that number.
Every result is checked against F(n).

## Versions

From `versions.csv`:

| name    | commit    | how a call works |
|---------|-----------|------------------|
| `copy`  | `44222a9` | parent of #1696: every call deep-copies the function item with Java serialization |
| `once`  | `a23c3c7` | parent of #1773: the body is serialized once and deserialized for every call |
| `plans` | `06814d0` | #1773: runtime plans and cursors |
| `final` | `4c7b372` | #1942 and #1943: the callee plan is reused, and static calls no longer copy the function |

Other changes were merged between these commits too, so comparing two of them, `plans` and `final` for
instance, shows everything that changed in between, not one PR alone. The query only makes static calls; the
dynamic and higher-order calls that #1943 also changed are not measured here.

## Running it

The scripts use the shared code in `../benchkit`, whose README explains how the timing works and what the CSV
contains.

```sh
./build.sh ../../rumble   # builds jars/<name>.jar for every version (needs Maven and JDK 17)
./run-all-jvm.sh          # times the query inside the JVM and records the bytes it allocates;
                          # copy at n = 28 and 30 runs in one JVM with 1 warm-up and 3 timed runs
                          # (8 and 21 minutes per run)
./memory/run-heap.sh      # the largest heap of each version and n (see memory/README.md)
python3 analyze.py        # medians and cost per call of the latest run
```

## Results (2026-10-22)

The run is in `data/jvm/run-2026-10-22T012629Z-11017/`. Each version and n ran in 3 JVMs, each with 2
untimed warm-up runs and 5 timed runs, with the versions interleaved and 12 GB of driver memory. `copy` at
n = 28 and 30 is in `large-copy/`: 1 JVM with 1 warm-up and 3 timed runs. The table shows the median of the
per-JVM medians, and in parentheses the spread between the JVMs ((max − min) / median):

| n  | calls     | copy              | once            | plans            | final            |
|----|-----------|-------------------|-----------------|------------------|------------------|
| 18 | 8,361     | 3.787 s (1%)      | 1.503 s (3%)    | 0.0150 s (5%)    | 0.0134 s (10%)   |
| 20 | 21,891    | 9.945 s (3%)      | 3.883 s (4%)    | 0.0229 s (9%)    | 0.0128 s (4%)    |
| 22 | 57,313    | 26.65 s (4%)      | 10.27 s (3%)    | 0.0482 s (4%)    | 0.0196 s (17%)   |
| 24 | 150,049   | 69.14 s (3%)      | 27.05 s (1%)    | 0.107 s (2%)     | 0.0350 s (5%)    |
| 26 | 392,835   | 178.4 s (1%)      | 71.17 s (3%)    | 0.277 s (2%)     | 0.0790 s (2%)    |
| 28 | 1,028,457 | 484.1 s (1 JVM)   |                 | 0.695 s (1%)     | 0.209 s (4%)     |
| 30 | 2,692,537 | 1,267 s (1 JVM)   |                 | 1.829 s (1%)     | 0.482 s (0%)     |

At the largest n, a call costs 471 µs in `copy` (n = 30), 181 µs in `once` (n = 26), 0.68 µs in `plans` and
0.18 µs in `final` (both n = 30). All results are correct.

`once` stops at n = 26 because it runs out of memory beyond that. In an earlier run (2026-10-14, same commit,
12 GB), every `once` JVM at n = 28 and n = 30 failed with an `OutOfMemoryError`; the logs are in
`data/logs/once-n28-*` and `once-n30-*`. That run timed whole `spark-submit` processes, which the code here
no longer supports, but the failure does not depend on how the time is measured.

## Why `once` runs out of memory

In short: in a recursion, `once` keeps every finished call alive until the query ends, about 22 KB per call.
#1696 keeps the body of a finished call at its call site so that the next call there can reuse it, but in a
recursion no call site is ever called twice. `memory/README.md` has the details, and `data/memory/` the GC
logs and heap histograms.

## Data

| Folder | Contents |
|---|---|
| `data/jvm/` | the run above |
| `data/memory/heap/` | the largest heap of each version and n (`memory/run-heap.sh`) |
| `data/memory/<version>-n<n>/` | GC logs and `jcmd` histograms of the live objects (`memory/run.sh`, 2026-10-17) |
| `data/logs/` | the `once` JVMs that ran out of memory at n = 28 and 30 |

`jars/` and `build/` are build outputs, and `build.sh` recreates them.
