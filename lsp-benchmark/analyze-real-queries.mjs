// Combines the runs of run-real-queries.sh.
// - Real queries: the time of a query is the median of its 5 timed runs in each process, and then
//   the median over the 3 processes. We report the median and the 99th percentile over all queries,
//   and how much these two statistics vary between processes ((slowest - fastest) / reported).
// - Cold start: the median of each step over the processes, and its variation between processes.
//
// Usage: node analyze-real-queries.mjs [data/real-queries]
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fmt, median, percentile, variation } from "./stats.mjs";
import { INVALID_TESTS } from "./test-queries.mjs";

const dir = process.argv[2] ?? "data/real-queries";
const pct = (x) => `${(100 * x).toFixed(0)}%`;
const load = (prefix, wrapper) =>
    readdirSync(dir)
        .filter((f) => f.startsWith(`${prefix}-`) && f.endsWith(`-${wrapper}.json`))
        .map((f) => JSON.parse(readFileSync(join(dir, f), "utf8")));

for (const wrapper of ["off", "on"]) {
    console.log(`\n== wrapper ${wrapper}`);

    const processes = load("real", wrapper);
    if (processes.length > 0) {
        // The runs in data/real-queries/ predate INVALID_TESTS and also timed runtime/Keywords2.jq; leave it out.
        const files = Object.keys(processes[0].times).filter((f) => !INVALID_TESTS.has(f));
        // Per process: the median of each query's timed runs.
        const perProcess = processes.map((p) => files.map((f) => median(p.times[f])));
        const combined = files.map((_, i) => median(perProcess.map((p) => p[i])));
        const m = median(combined);
        const p99 = percentile(combined, 0.99);
        const slowest = files.map((f, i) => [combined[i], f]).sort((a, b) => b[0] - a[0]).slice(0, 3);
        console.log(`real queries: ${files.length} queries, ${processes.length} processes × ${processes[0].reps} runs (after ${processes[0].warmup} warm-up passes)`);
        console.log(`  median ${fmt(m)} (variation ${pct(variation(perProcess.map(median), m))})`);
        console.log(`  p99    ${fmt(p99)} (variation ${pct(variation(perProcess.map((p) => percentile(p, 0.99)), p99))})`);
        console.log(`  max    ${fmt(Math.max(...combined))}; slowest: ${slowest.map(([ms, f]) => `${f} ${fmt(ms)}`).join(", ")}`);
    }

    const cold = load("cold", wrapper).flatMap((c) => c.rounds);
    if (cold.length > 0) {
        console.log(`cold start: ${cold.length} processes`);
        for (const [name, get] of [
            ["initialize", (r) => r.initializeMs],
            ["first diagnostics", (r) => r.first.ms],
            ["next diagnostics", (r) => r.second.ms],
            ["first Parquet query", (r) => r.sparkFirst.ms],
            ["next Parquet check", (r) => r.sparkSecond.ms],
        ]) {
            const xs = cold.map(get);
            const m = median(xs);
            console.log(`  ${name.padEnd(20)} ${fmt(m)} (${fmt(Math.min(...xs))} to ${fmt(Math.max(...xs))}, variation ${pct(variation(xs, m))})`);
        }
    }
}
