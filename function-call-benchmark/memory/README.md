# Why `once` runs out of memory

`run.sh VERSION N [INTERVAL] [DRIVER_MEMORY]` runs `local:fib(N)` once from the command line with a GC log
(`-Xlog:gc`). Every INTERVAL seconds it also takes a histogram of the live objects with
`jcmd GC.class_histogram`, which runs a full GC first. The output goes to `data/memory/<version>-n<N>/`.

These are the runs of 2026-10-17, all with 12 GB of driver memory:

```sh
./memory/run.sh plans 30 1 && ./memory/run.sh once 26 15 && ./memory/run.sh copy 26 30 && ./memory/run.sh once 28 30
```

`python3 memory/histograms.py` reads these folders and prints, for every histogram, the heap after the GCs
around it, the live bytes and the number of `RuntimeStaticContext` objects. The tables below come from it.
With `--save`, it writes them to `summary.txt` and `summary.csv` in each folder, where they already are.

## What they show

The GC logs count in MiB (2^20 bytes).

| Run | Heap after the last GC | `RuntimeStaticContext` objects alive |
|---|---|---|
| `copy`, n = 26 (392,835 calls) | 67 MiB | 574 |
| `plans`, n = 30 (2,692,537 calls) | 66 MiB | 57 |
| `once`, n = 26 | 7,806 MiB | 1.2 M after 15 s, 2.7 M after 30 s, 4.2 M after 45 s, 5.7 M after 60 s |
| `once`, n = 28 | out of memory after 814 s (exit code 46) | |

Because `jcmd` runs a full collection before each histogram, these runs also show how far a young collection
overstates the live heap. That matters for `heap.py` further down, which looks at all collections. For
`once` at n = 26 (`data/memory/once-n26/`):

| Histogram | Heap after the young GC before it | After the full GC | Live objects in the histogram |
|---|---|---|---|
| 15 s | 1,525 MiB | 1,425 MiB | 1.48 GB |
| 30 s | 3,107 MiB | 3,043 MiB | 3.17 GB |
| 45 s | 4,843 MiB | 4,676 MiB | 4.88 GB |
| 60 s | 6,412 MiB | 6,290 MiB | 6.57 GB |

A full collection frees only 2–7% more than the young collection just before it, so the young collections
are a fair measure here.

In `once`, the live heap grows steadily during the query, by about 20 KB per call. Per call, that is about
18 `RuntimeStaticContext` objects with their maps, sets and source positions (`ExceptionMetadata`,
`SourceRange`, `SourcePosition`). At that rate, n = 26 needs about 8 GB, which fits in 12 GB but not in 4 GB,
and n = 28 (1,028,457 calls) needs about 20 GB. This fits every out-of-memory error in the benchmark.

## The cause

#1696, the first commit after `copy`, made `FunctionItemCallIterator` hold on to the body iterator of a call
that finished normally, so the next call at the same call site could reuse it ("Preserve a normally
exhausted body for reuse", in `closeLocal`). But each call deserializes its own copy of the body, and that
copy has its own call sites for the recursive calls, which hold on to the bodies they created in turn. In a
recursion no call site is called twice, so nothing is ever reused, and every finished body stays reachable
from its parent. The whole call tree, about 18 iterators with their static contexts per call, lives until
the query ends. It is freed between queries, which is why seven runs of n = 26 in one JVM in
`run-all-jvm.sh` did not run out of memory.

`copy` has no such cache, and with runtime plans (`plans`) a call only creates a cursor, which is dropped
when the call returns.

## Largest heap per version and n

`run-heap.sh` runs `local:fib(n)` once per version and n, with 12 GB of driver memory and a GC log but no
histograms. `heap.py` then prints the largest heap after any GC. Young collections count too, which makes it
a slight overestimate (see above). Like the other runs, it writes a `manifest.json` with the commit, the jar
and query hashes, the command and the environment, checks the result, and stops a run after one hour
(`--timeout SECONDS`).

`data/memory/heap/run-2026-10-22T063139Z-14564/` (2026-10-22), in MiB:

| n  | calls     | copy | once  | plans | final |
|----|-----------|------|-------|-------|-------|
| 20 | 21,891    | 68   | 699   | 67    | 68    |
| 22 | 57,313    | 68   | 1,263 | 67    | 68    |
| 24 | 150,049   | 72   | 3,107 | 67    | 68    |
| 26 | 392,835   | 72   | 8,447 | 67    | 70    |
| 28 | 1,028,457 |      |       | 67    | 68    |
| 30 | 2,692,537 |      |       | 68    | 68    |

`once` grows by about 22 KB per call ((8,447 − 68) MiB / 392,835 calls). `copy`, `plans` and `final` stay at
the size of Spark and RumbleDB without any query. The thesis gives these values in MB (×1.048576). All
results are correct. `once` at n = 28 and 30 runs out of memory (see `../README.md`), and `copy` is not run
beyond n = 26: it takes 8 and 21 minutes there, and its heap does not grow anyway.

```sh
./memory/run-heap.sh           # new runs go in data/memory/heap/run-<UTC time>-<pid>/
python3 memory/heap.py         # the latest run, or: python3 memory/heap.py RUN_DIRECTORY
```

`run-heap.sh` ends with `heap.py --save`, which writes the table to `summary.txt` and `summary.csv` in the run
directory.
