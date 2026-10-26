// Combines the rounds of run-latency.sh, in the same way as the RumbleDB benchmarks:
// - median:  the median of the per-process medians;
// - spread:  (slowest - fastest per-process median) / median, the variation between processes;
// - p95:     the 95th percentile over all timed runs of all processes.
//
// Usage: node analyze-latency.mjs [data/latency]
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fmt, median, percentile, variation } from "./stats.mjs";

const dir = process.argv[2] ?? "data/latency";

/** Combines one measurement (a list of timed runs per process). */
function combine(runsPerProcess) {
    const medians = runsPerProcess.map(median);
    const m = median(medians);
    return {
        median: m,
        spread: variation(medians, m),
        p95: percentile(runsPerProcess.flat(), 0.95),
        processes: medians.length,
    };
}

const show = (c) => `${fmt(c.median)} (±${(100 * c.spread).toFixed(0)}%, p95 ${fmt(c.p95)})`;

for (const configuration of ["off", "on"]) {
    const files = readdirSync(dir).filter((f) => f.startsWith("round-") && f.endsWith(`-${configuration}.json`)).sort();
    if (files.length === 0) continue;
    const rounds = files.map((f) => JSON.parse(readFileSync(join(dir, f), "utf8")));
    console.log(`\n== wrapper ${configuration}: ${rounds.length} processes × ${rounds[0].reps} runs (after ${rounds[0].warmup} warm-up runs)`);

    for (const size of Object.keys(rounds[0].sizes)) {
        const per = rounds.map((r) => r.sizes[size]);
        console.log(`${size} lines`);
        console.log(`  diagnostics          ${show(combine(per.map((s) => s.diagnostics)))}`);
        for (const name of Object.keys(per[0].completion)) {
            const items = [...new Set(per.map((s) => s.completion[name].itemCount))].join("/");
            console.log(`  completion ${name.padEnd(9)} ${show(combine(per.map((s) => s.completion[name].times)))}  [${items} items]`);
        }
    }

    const refs = rounds.map((r) => r.references);
    const counts = [...new Set(refs.flatMap((r) => [r.firstCount, r.count]))].join("/");
    console.log(`references (${refs[0].files} files, expected ${refs[0].expected}, found ${counts})`);
    console.log(`  first request        ${fmt(median(refs.map((r) => r.firstMs)))} (per process: ${refs.map((r) => fmt(r.firstMs)).join(", ")})`);
    console.log(`  later requests       ${show(combine(refs.map((r) => r.later)))}`);
}
