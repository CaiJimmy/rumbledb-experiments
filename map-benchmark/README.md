# Maps: building a map with map:put

How long does it take, and how much memory, to build a map one entry at a time? This benchmark compares three
ways RumbleDB has stored maps: layers without compaction, layers flattened every 32 updates (#1771), and
persistent hash tries (#1975). In the thesis, maps are described in the section "Immutable maps" of chapter 3
and measured in the Evaluation chapter.

## Query

`queries/size.xq.template`, where `run.py` fills in `{n}`:

```xquery
xquery version "3.1";
let $m := fold-left(1 to {n}, map {}, function($m, $i) { map:put($m, $i, $i) })
return map:size($m)
```

It builds an n-entry map with `fold-left` and `map:put` and returns its size, which is checked on every run.

For the memory of the map, `queries/map.xq.template` does the same `fold-left` but returns the map itself
(see "Memory" below).

## Versions

| name | commit | maps |
|---|---|---|
| `layered` | `0897c0cd4` | layers without compaction; the size is recomputed through the layers |
| `compacted-initial` | `753e669ef` | #1771: the size is cached, and the layers are compacted after 32 |
| `compacted` | `4c7b3724a` | compacted maps on master just before #1975 |
| `trie` | `04b193dc9` | #1975 merged: persistent hash tries |

`layered` against `compacted-initial` shows the effect of compaction, and `compacted` against `trie` the
effect of tries. Both compaction versions are run because a lot changed between them, including the
function-call work that `fold-left` relies on. [map-versions.md](../map-versions.md) lists all five map
versions; the fifth, `trie-hashed`, is only used by the date-key benchmark.

## Why building a map was so slow before #1771

Every type check on a map calls `getSize()` to see whether the map is empty
(`InstanceOfIterator.doesItemTypeMatchItem`), and that includes checking the first argument of `map:put`.
Before #1771, `getSize()` on a layer called `hasKey` on the map below it, which goes through all lower layers,
and then `getSize()` on the map below. One call cost O(k^2) for a chain of k layers, and building n entries
O(n^3). I found this by sampling `jstack` while the `layered` jar ran with n = 8,000.

After #1771, `getSize()` takes constant time, but every 32 updates the chain is copied into a flat map, so
building n entries still copies O(n^2 / 32) entries in total.

## Memory

Both numbers are measured by `QueryBench` inside the JVM (see `../benchkit/README.md`):

- **Allocated bytes**, recorded with every timed run: what the thread evaluating the query allocates, which is
  the garbage that building the map produces. In `compacted-initial`, that is mostly the copies of the flat
  map every 32 updates; in `trie`, the copied trie paths.
- **Retained bytes**, from `run-all-retained.sh`: how much memory the finished map takes. The harness runs
  `queries/map.xq.template`, keeps the map alive, and compares the heap after a full GC with the map against
  the heap after a full GC before the query. For `layered`, this is the whole chain of layers; for
  `compacted-initial`, the flat map plus at most 32 layers.

The largest heap after a GC, which the Fibonacci benchmark uses, does not work here. A map of 64,000 entries
takes about 10 MB, which is small next to the 70 MB or so that Spark and RumbleDB use, and next to how much
that varies between runs. In the retained run below, a map with one entry came out at 0.4–4.3 KB, so the
measurement is good to a few KB.

## Running it

The scripts use the shared code in `../benchkit`, whose README explains the modes and the CSV.

```sh
./build.sh ../../rumble   # builds jars/<name>.jar for every version (needs Maven and JDK 17)
                          # ./build.sh ../../rumble compacted,trie builds only some versions
./run-all-jvm.sh          # times the query inside the JVM and records the bytes it allocates
./run-all-retained.sh     # measures the memory of the finished map
python3 analyze.py        # medians of the latest timed and memory runs
```

Both runs go up to n = 4,000 for `layered`, 64,000 for the two compaction versions, and 512,000 for `trie`.

## Time and allocation (2026-10-21)

The run is in `data/jvm/run-2026-10-21T230158Z-1057/`: 3 JVMs per version and n, each with 2 untimed warm-up
runs and 5 timed runs, versions interleaved, 4 GB of driver memory. The table shows the median of the
per-JVM medians, and in parentheses the spread between the JVMs:

| n       | layered        | compacted-initial | compacted      | trie           |
|---------|----------------|-------------------|----------------|----------------|
| 1,000   | 0.874 s (3%)   | 0.0233 s (19%)    | 0.0251 s (14%) | 0.0115 s (6%)  |
| 2,000   | 8.519 s (1%)   | 0.0570 s (11%)    | 0.0625 s (3%)  | 0.0166 s (14%) |
| 4,000   | 84.33 s (1%)   | 0.182 s (11%)     | 0.186 s (8%)   | 0.0188 s (11%) |
| 8,000   |                | 0.680 s (7%)      | 0.655 s (1%)   | 0.0230 s (11%) |
| 16,000  |                | 2.575 s (3%)      | 2.667 s (6%)   | 0.0257 s (16%) |
| 32,000  |                | 10.40 s (7%)      | 10.79 s (6%)   | 0.0363 s (10%) |
| 64,000  |                | 41.72 s (8%)      | 44.17 s (4%)   | 0.0637 s (3%)  |
| 128,000 |                |                   |                | 0.137 s (3%)   |
| 256,000 |                |                   |                | 0.262 s (6%)   |
| 512,000 |                |                   |                | 0.523 s (9%)   |

Memory allocated by the query (median of the per-JVM medians):

| n       | layered  | compacted-initial | compacted | trie     |
|---------|----------|-------------------|-----------|----------|
| 1,000   | 13.2 GB  | 147 MB            | 151 MB    | 7.5 MB   |
| 2,000   | 106 GB   | 580 MB            | 583 MB    | 10.8 MB  |
| 4,000   | 851 GB   | 2.30 GB           | 2.31 GB   | 17.0 MB  |
| 8,000   |          | 9.29 GB           | 9.29 GB   | 29.5 MB  |
| 16,000  |          | 37.3 GB           | 37.3 GB   | 53.0 MB  |
| 32,000  |          | 149 GB            | 149 GB    | 102 MB   |
| 64,000  |          | 597 GB            | 597 GB    | 202 MB   |
| 128,000 |          |                   |           | 407 MB   |
| 256,000 |          |                   |           | 815 MB   |
| 512,000 |          |                   |           | 1.64 GB  |

Each time n doubles, `layered` gets about 10 times slower (cubic), and the two compaction versions about 4
times slower from 8,000 on (quadratic). `trie` takes about twice as long from 64,000 on, roughly 1 µs and
3.2 KB per entry. `layered` stops at n = 4,000, which already takes 84 s. All results are correct.

## Memory of the finished map (2026-10-22)

The run is in `data/retained/run-2026-10-22T001851Z-3064/`: 3 JVMs per version and n, each with 1 warm-up and
2 measured runs. At n = 64,000, the map takes 10.32 MB in `compacted-initial`, 10.32 MB in `compacted` and
10.15 MB in `trie`; at n = 512,000, 78.1 MB in `trie`. `layered` at n = 4,000 takes 0.50 MB, against
0.63–0.65 MB for the other versions. `python3 analyze.py` prints the whole table.

## Microbenchmark (one JVM, no Spark)

This check from 2026-10-15 only explains the times of `layered` and `compacted-initial`; it does not compile
against `trie`, where `ItemFactory.createMapItemAddingKey` takes a fourth argument (`mutable`).

`microbenchmark/MapBench.java` calls `ItemFactory.createMapItemAddingKey(map, key, value)` n times, with or
without a `getSize()` before each call, like the type check of `map:put`. The results are in
`microbenchmark/results-2026-10-15.txt`, which calls the two versions `before` and `after`:

- `layered` without `getSize()`: 128,000 puts in about 1 ms, so the layers themselves are cheap.
- `layered` with `getSize()`: 0.9 s, 9.0 s and 88.5 s for n = 1,000, 2,000 and 4,000, in line with the Spark
  runs.
- `compacted-initial`, with or without `getSize()`: 3.6 s, 13.7 s, 50.8 s and 232 s for n = 16,000 to
  128,000. The cost is the copy every 32 updates, again in line with the Spark runs.

```sh
cd microbenchmark
javac -cp ../jars/compacted-initial.jar MapBench.java
java -Xss512m -Xmx4g -cp ../jars/compacted-initial.jar:. MapBench size 16000 32000 64000   # or: nosize; or ../jars/layered.jar
```

## Data

| Folder | Contents |
|---|---|
| `data/jvm/` | the timed run above |
| `data/retained/` | the memory run above |

`jars/` and `build/` are build outputs, and `build.sh` recreates them.
