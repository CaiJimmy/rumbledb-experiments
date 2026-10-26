# Maps: building a map with map:merge

`../map-benchmark` builds a map one entry at a time with `map:put`. Here the whole map is built in a single
`map:merge`, to see what hash tries cost when a map is built in bulk.

In both versions, `map:merge` first collects the entries in a `java.util.HashMap`. `compacted` then builds one
flat map from it, and `trie` (#1975) one persistent hash trie, which later `map:put` and `map:remove` calls
can share. Scala's `HashMap` builder updates the trie in place until it is done, so building it copies no
paths.

## Query

`queries/size.xq.template`, where `run.py` fills in `{n}`:

```xquery
xquery version "3.1";
map:size(map:merge(for $i in 1 to {n} return map { $i : $i }))
```

`queries/map.xq.template` is the same without `map:size`. The memory run uses it to measure the map itself
(see `../map-benchmark/README.md`).

## Versions

From `versions.csv`:

| name   | commit      | map:merge |
|--------|-------------|-----------|
| `compacted` | `4c7b3724a` | master just before #1975: a `java.util.HashMap`, then one flat `MapItem` |
| `trie` | `04b193dc9` | #1975: a `java.util.HashMap`, then one trie, built in place by Scala's `HashMap` builder |

The only difference between the two commits is the map implementation (see
[map-versions.md](../map-versions.md)). `jars/` is a link to `../map-benchmark/jars`.

## Running it

```sh
../map-benchmark/build.sh ../../rumble compacted,trie  # or ./build.sh, which builds the same jars
./run-all-jvm.sh         # time and allocated bytes, n = 1,000 and 512,000
./run-all-retained.sh    # memory of the finished map
python3 analyze.py       # medians of the latest timed and memory runs
```

Both together take a few minutes.

## Results (2026-10-23)

The timed run is in `data/jvm/run-2026-10-23T105657Z-52402/` (3 JVMs per version and n, each with 2 warm-up
and 5 timed runs), and the memory run in `data/retained/run-2026-10-23T105748Z-52402/` (3 JVMs, each with 1
warm-up and 2 runs), both with 4 GB of driver memory. The table shows the median of the per-JVM medians, and
in parentheses the spread between the JVMs:

| n       | compacted       | trie            | allocated (compacted / trie) | retained (compacted / trie) |
|---------|-----------------|-----------------|------------------------------|-----------------------------|
| 1,000   | 0.0110 s (12%)  | 0.0127 s (12%)  | 5.7 / 5.9 MB                 |                             |
| 512,000 | 0.322 s (8%)    | 0.376 s (0%)    | 1,038 / 1,086 MB             | 72.0 / 77.5 MB              |

At n = 512,000, `trie` takes 17% longer, and its map takes 8% more memory. All results are correct. Take the
time difference with a grain of salt: an earlier run of the same commits (2026-10-22, not kept) gave 0.298 s
against 0.371 s (+24%).
