// Time to the first diagnostics of each valid test query of the correctness experiment, in ONE
// server process: WARMUP untimed passes over all queries, then REPS timed passes. Every open uses
// a new document version, so that no cached result of an earlier pass is reused.
// run-real-queries.sh starts this script in several processes.
//
// Usage: node real-queries.mjs <on|off> <out.json>
// Environment: WARMUP (default 2), REPS (default 5); the queries are the valid queries of
// data/correctness-final-on.json that the evaluation uses (test-queries.mjs).
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { LspClient, parseArgs } from "./lsp-client.mjs";
import { TEST_FILES, isEvaluated, runnerLanguage } from "./test-queries.mjs";

const { wrapper, outPath } = parseArgs("real-queries.mjs");
const WARMUP = Number(process.env.WARMUP ?? 2);
const REPS = Number(process.env.REPS ?? 5);

const correctness = JSON.parse(readFileSync(join(import.meta.dirname, "data", "correctness-final-on.json"), "utf8"));
const queries = correctness.results
    .filter((r) => r.set === "valid" && isEvaluated(r))
    .map((r) => ({ file: r.file, text: readFileSync(join(TEST_FILES, r.file), "utf8") }));

const client = new LspClient({ rootPath: TEST_FILES, wrapper });
await client.start();

async function timeFirstDiagnostics({ file, text }) {
    const path = join(TEST_FILES, file);
    const uri = pathToFileURL(path).href;
    const published = client.nextDiagnostics(uri);
    const start = performance.now();
    client.open(uri, text, runnerLanguage(file));
    await published;
    const ms = performance.now() - start;
    client.close(uri);
    return ms;
}

const times = Object.fromEntries(queries.map((q) => [q.file, []]));
for (let pass = 0; pass < WARMUP + REPS; pass++) {
    for (const query of queries) {
        const ms = await timeFirstDiagnostics(query);
        if (pass >= WARMUP) times[query.file].push(ms);
    }
    console.error(`  pass ${pass + 1} of ${WARMUP + REPS} done`);
}

await client.stop();
writeFileSync(outPath, JSON.stringify({ wrapper, warmup: WARMUP, reps: REPS, times }));
process.exit(0);
