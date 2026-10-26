# Map versions

The map benchmarks compare five commits of RumbleDB master.

| Name                | Commit                                     | What it is                                     |
| ------------------- | ------------------------------------------ | ---------------------------------------------- |
| `layered`           | `0897c0cd44b694f89eb4b5bae8979461092a0f78` | Before compaction                              |
| `compacted-initial` | `753e669ef9d30f5be8368da1909d22612aeb9d36` | Compaction as #1771 introduced it              |
| `compacted`         | `4c7b3724a45ea68bacef0ec566b6409dabe1632f` | Master just before hash tries were merged      |
| `trie`              | `04b193dc9c19623e3dae95efb0ca59de39b72670` | #1975 merged: hash tries                       |
| `trie-hashed`       | `bc9593196679b597f05a508f9a83e19da2330f7d` | #1978 merged: better hashes for some key types |

## Which benchmark compares which

| Benchmark                                    | Versions                                            |
| -------------------------------------------- | --------------------------------------------------- |
| Integer keys with `map:put`, time and memory | `layered`, `compacted-initial`, `compacted`, `trie` |
| Date keys with `map:put`, time and memory    | `trie`, `trie-hashed`                               |
| `map:merge`, time and memory                 | `compacted`, `trie`                                 |
| `map:get`, time                              | `compacted`, `trie`                                 |

`layered` against `compacted-initial` shows what compaction changed, and `compacted` against `trie` what
tries changed (`compacted` is the parent of `trie`). The two compaction versions are months apart, and other
changes went in between, such as the function-call work that `fold-left` benefits from, so a difference
between them is not only about maps. The thesis reports `layered`, `compacted` and `trie`.

## Building

From the root of this repository, these two commands build all five jars:

```sh
./map-benchmark/build.sh ../rumble
./map-date-key-benchmark/build.sh ../rumble trie-hashed
```

All map benchmarks share `map-benchmark/jars/`. Each build script builds the versions listed in its own
`versions.csv`.
