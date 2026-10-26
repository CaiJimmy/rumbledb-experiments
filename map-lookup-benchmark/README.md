# Maps: looking up keys with map:get

The other map benchmarks build maps; this one reads from one. It builds a map of 512,000 entries once with
`map:merge` and then calls `map:get` on it n times. In `compacted`, a lookup finds the index of the key in a
`java.util.HashMap` and then reads a list. In `trie` (#1975), it is a lookup in Scala's immutable `HashMap`,
which goes down at most a few levels of the trie.

## Query

`queries/lookup.xq.template`, where `run.py` fills in `{n}`:

```xquery
xquery version "3.1";
let $m := map:merge(for $k in 1 to 512000 return map { $k : 1 })
return sum(for $i in 1 to {n} return map:get($m, $i mod 512000 + 1))
```

Every value is 1, so the result is n. The lookups go through the keys in the order they were inserted.
`queries/lookup-scattered.xq.template` looks up `($i * 7919) mod 512000 + 1` instead, so two lookups in a
row are 7,919 keys apart. 7,919 is a prime that does not divide 512,000, so every key is still looked up
equally often.

n = 1 is essentially the time to build the map. The cost of one lookup is
(t(n = 10,000,000) − t(n = 1)) / 10,000,000. Note that `analyze.py` prints the time at n = 10,000,000 divided
by n, with the build still in it.

## Versions

From `versions.csv`:

| name   | commit      | lookup |
|--------|-------------|--------|
| `compacted` | `4c7b3724a` | master just before #1975: a `HashMap<Item, Integer>` of indexes into a list of values |
| `trie` | `04b193dc9` | #1975: Scala's immutable `HashMap<Item, Entry>` |

The only difference between the two commits is the map implementation (see
[map-versions.md](../map-versions.md)). `jars/` is a link to `../map-benchmark/jars`.

## Running it

```sh
../map-benchmark/build.sh ../../rumble compacted,trie  # or ./build.sh, which builds the same jars
./run-all-jvm.sh         # n = 1 and 10,000,000, first in insertion order, then 7,919 apart
python3 analyze.py data/jvm/RUN_DIRECTORY/insertion-order
```

Both orders together take about 25 minutes.

## Results (2026-10-23)

3 JVMs per version and n, each with 2 warm-up and 5 timed runs, 4 GB of driver memory. The table shows the
median of the per-JVM medians, and in parentheses the spread between the JVMs:

| Order | Run | n | compacted | trie |
|---|---|---|---|---|
| insertion order | `data/jvm/run-2026-10-23T112356.184295Z-2f1c3c68/` | 1 | 0.296 s (5%) | 0.349 s (4%) |
| | | 10,000,000 | 6.031 s (8%) | 8.698 s (23%) |
| keys 7,919 apart | `data/jvm/run-2026-10-23T113629.205349Z-5ad7a5ca/` | 1 | 0.311 s (3%) | 0.363 s (15%) |
| | | 10,000,000 | 8.019 s (18%) | 8.858 s (5%) |

One lookup costs 0.574 µs in `compacted` and 0.835 µs in `trie` (+46%) in insertion order, and 0.771 µs
against 0.849 µs (+10%) with keys 7,919 apart. The order makes little difference to `trie`, but `compacted`
is faster in insertion order, probably because Java's `HashMap` keeps consecutive integer keys close together
in memory. All results are correct.

The JVMs disagree quite a bit, and so do separate runs: an earlier insertion-order run of the same commits
(not kept) gave 0.640 µs against 0.844 µs (+32%).
