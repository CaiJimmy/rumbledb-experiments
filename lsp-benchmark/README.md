# Language-server benchmark

Evaluation of the JSONiq language server in Section 5.4 of the thesis: are its diagnostics correct, and is it
fast enough to use while typing? The scripts talk to the server over stdio as an editor does (`lsp-client.mjs`),
with the RumbleDB wrapper disabled (`off`) or enabled (`on`, needs Java 17).

## Requirements

- Node.js (the results were measured with Node.js 26.12); the scripts have no npm dependencies.
- The language server, built: in `jsoniq-lsp/packages/language-server`, `pnpm run build`. The thesis measures
  language server 2.18.0 with wrapper 0.14.0.
- `jsoniq-lsp/` and `rumble/` next to this repository (see `SERVER` in `lsp-client.mjs` and `TEST_FILES` in
  `test-queries.mjs`). The correctness experiments read RumbleDB's test queries
  (`rumble/src/test/resources/test_files`); the cold start reads a Parquet file of its test resources.

## Correctness

Diagnostics on RumbleDB's test queries, compared with the expectation in each file's `(:JIQS: …:)` header.
`test-queries.mjs` decides which tests are evaluated and in which language each file is opened.

```sh
node correctness.mjs off data/correctness-final-off.json
node correctness.mjs on  data/correctness-final-on.json
node analyze-correctness.mjs data/correctness-final-on.json     # -v lists the files
```

Type errors: `node type-errors.mjs <on|off> <out.json>` opens the tests of the `static-typing/` folder that
expect an error (RumbleDB runs them with static typing) and records the diagnostics.

## Response times

Generated queries of 100 to 10,000 lines (`workloads.mjs`) and a workspace of 101 files for find references.
`latency.mjs` measures one server process: diagnostics after an edit, completion right after typing a trigger,
and find references, each with 3 warm-up runs and 20 timed runs.

```sh
sh run-latency.sh [out-dir] [configurations]   # default: data/latency "off on"; about 35 minutes
node analyze-latency.mjs [out-dir]             # median of the per-process medians, spread, p95
```

Real queries and cold start: `run-real-queries.sh` times the first diagnostics of every valid test query in
3 processes × (2 warm-up + 5 timed passes), then starts 10 new server processes per configuration
(`cold-start.mjs`), alternating. Analyze with `node analyze-real-queries.mjs`.

Run on an idle machine on mains power, without compiling anything meanwhile.

## Data

The thesis numbers:

| Thesis | Data |
|---|---|
| Correctness table, first two rows | `data/correctness-final-<off\|on>.json` |
| Correctness table, static-typing row | `data/type-errors-<off\|on>.json` (132 tests) |
| Response-time table, without wrapper; find references | `data/latency/round-<n>-off.json` |
| Response-time table, with wrapper | `data/latency-2.18.0/round-<n>-on.json` |
| Real queries, start-up table | `data/real-queries/` |

All of them use language server 2.18.0 with wrapper 0.14.0. Wrapper 0.14.0 runs RumbleDB commit `a8689ea13`
(branch `perf/lexer-predicate-at-right-edge`), which adds a fix of the lexer's performance to master.

`data/work/` and `data/server-cwd/` hold scratch files of the server and the wrapper; they are not in the
repository.
