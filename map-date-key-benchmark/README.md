# Maps: date keys

The same as `../map-benchmark`, a map built one entry at a time with `map:put`, but with `xs:date` keys
instead of integers. In #1975, every date key had the same hash, so they all landed in one collision node of
the trie, where each `map:put` compares the new key with all the others. #1978 hashes a date by its instant.
This benchmark measures the time and memory of both. The thesis does not report it.

## Query

`queries/size.xq.template`, where `run.py` fills in `{n}`:

```xquery
xquery version "3.1";
let $m := fold-left(1 to {n}, map {}, function($m, $i) {
  map:put($m, xs:date("2000-01-01") + xs:dayTimeDuration("P" || $i || "D"), $i)
})
return map:size($m)
```

The keys are n consecutive days, so no two are equal. `queries/map.xq.template` is the same without
`map:size`. The memory run uses it to measure the map itself (see `../map-benchmark/README.md`).

## Versions

From `versions.csv`:

| name     | commit      | date keys |
|----------|-------------|-----------|
| `trie`   | `04b193dc9` | #1975: every date key has the same hash (`AtomicItemEquivalence.hash` returns `0x47`) |
| `trie-hashed` | `bc9593196` | #1978 merged: a date key is hashed by its instant |

The two commits differ in the hashing in `AtomicItemEquivalence` and its Java and XQuery tests. Integer keys,
as in `../map-benchmark`, are hashed by `numericHash`, which #1978 leaves alone. `jars/` is a link to
`../map-benchmark/jars`, which also holds `trie`. [map-versions.md](../map-versions.md) lists all five map
versions.

## Running it

```sh
./build.sh ../../rumble trie-hashed   # builds jars/trie-hashed.jar (../map-benchmark/build.sh builds trie)
./run-all-jvm.sh                 # time and allocated bytes; trie stops at n = 32,000
./run-all-retained.sh            # memory of the finished map
python3 analyze.py               # medians of the latest timed and memory runs
```

Both together take about 15 minutes.

## Results (2026-10-22)

The runs are in `data/jvm/run-2026-10-22T005352Z-5020/` and `data/retained/run-2026-10-22T010335Z-5847/`:
3 JVMs per version and n (2 warm-up and 5 timed runs for time, 1 warm-up and 2 runs for memory), 4 GB of
driver memory. The table shows the median of the per-JVM medians, and in parentheses the spread between the
JVMs:

| n      | trie            | trie-hashed     | allocated (trie / trie-hashed) | retained (trie / trie-hashed) |
|--------|-----------------|-----------------|--------------------------------|-------------------------------|
| 1,000  | 0.0437 s (3%)   | 0.0222 s (8%)   | 37 / 37 MB                     | 0.25 / 0.25 MB                |
| 2,000  | 0.115 s (15%)   | 0.0329 s (8%)   | 69 / 69 MB                     |                               |
| 4,000  | 0.407 s (10%)   | 0.0539 s (14%)  | 131 / 132 MB                   | 0.98 / 1.01 MB                |
| 8,000  | 1.242 s (8%)    | 0.0668 s (23%)  | 257 / 256 MB                   |                               |
| 16,000 | 4.191 s (1%)    | 0.108 s (7%)    | 510 / 506 MB                   | 3.92 / 3.96 MB                |
| 32,000 | 15.75 s (1%)    | 0.200 s (3%)    | 1,014 / 1,008 MB               | 7.84 / 8.12 MB                |
| 64,000 |                 | 0.402 s (2%)    | – / 2,014 MB                   | – / 16.4 MB                   |

With one hash for every date, `trie` gets 3 to 4 times slower each time n doubles, since every `map:put`
compares the new key with all the others in the collision node. `trie-hashed` takes about twice as long per
doubling from 16,000 on. Both allocate and keep about the same memory: the collision node costs key
comparisons, not memory. All results are correct.
