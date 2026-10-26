// Latency of the language server, measured at the client, in ONE server process.
// run-latency.sh starts this script several times to get independent processes.
//
// Usage: node latency.mjs <on|off> <out.json>      (on/off: RumbleDB wrapper)
// Environment: SIZES (default 100,1000,5000,10000), WARMUP (default 3), REPS (default 20)
//
// The output keeps the time of every timed run, in milliseconds, so that analyze-latency.mjs can
// combine several processes.
import { rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { LspClient, parseArgs } from "./lsp-client.mjs";
import { LIBRARY_TEXT, generateQuery, writeReferencesWorkspace } from "./workloads.mjs";

const { wrapper, outPath } = parseArgs("latency.mjs");
const SIZES = (process.env.SIZES ?? "100,1000,5000,10000").split(",").map(Number);
const WARMUP = Number(process.env.WARMUP ?? 3);
const REPS = Number(process.env.REPS ?? 20);
const MAIN_MODULES = 100;

const workDir = join(import.meta.dirname, "data", "work", wrapper ? "on" : "off");
rmSync(workDir, { recursive: true, force: true });
writeReferencesWorkspace(join(workDir, "workspace"), MAIN_MODULES);

const client = new LspClient({ rootPath: workDir, wrapper, cwd: join(workDir, "server-cwd") });
await client.start();

/** Runs `once` WARMUP + REPS times; `once(i)` returns the measured time of run i. Returns the timed runs. */
async function repeat(once) {
    const times = [];
    for (let i = 0; i < WARMUP + REPS; i++) {
        const ms = await once(i);
        if (i >= WARMUP) times.push(ms);
    }
    return times;
}

const results = { wrapper, warmup: WARMUP, reps: REPS, sizes: {}, references: null };

for (const size of SIZES) {
    const path = join(workDir, `generated-${size}.jq`);
    const uri = pathToFileURL(path).href;
    const valid = generateQuery(size);
    writeFileSync(path, valid.text);

    // Open the file and check that it is valid.
    const opened = client.nextDiagnostics(uri);
    client.open(uri, valid.text);
    const errors = ((await opened) ?? []).filter((d) => d.severity === undefined || d.severity === 1);
    if (errors.length > 0) throw new Error(`generated-${size}.jq has errors: ${errors[0].message}`);

    // Diagnostics: change one digit, which keeps the file valid, and wait for the new diagnostics.
    const diagnostics = await repeat(async (i) => {
        const published = client.nextDiagnostics(uri);
        const start = performance.now();
        client.change(uri, generateQuery(size, { digit: i % 10 }).text);
        await published;
        return performance.now() - start;
    });

    // Completion: type a trigger in the middle function and request completion right away. The time
    // runs from the edit to the completion response, so it includes the server's processing of the
    // edit. The diagnostics of the edit are awaited outside the timed region.
    const triggers = { variable: "return $", function: "return local:" };
    if (wrapper) triggers.field = `let $o := { "id": $z, "name": $s } return $o.`;
    const completion = {};
    for (const [name, returnClause] of Object.entries(triggers)) {
        const { text, returnLine } = generateQuery(size, { returnClause });
        const position = { line: returnLine, character: `  ${returnClause}`.length };
        let itemCount = 0;
        const times = await repeat(async () => {
            const published = client.nextDiagnostics(uri);
            const start = performance.now();
            client.change(uri, text);
            const result = await client.request("textDocument/completion", { textDocument: { uri }, position });
            const ms = performance.now() - start;
            itemCount = (Array.isArray(result) ? result : (result?.items ?? [])).length;
            await published;
            return ms;
        });
        completion[name] = { itemCount, times };
    }

    client.close(uri);
    results.sizes[size] = { lines: valid.text.split("\n").length - 1, diagnostics, completion };
    console.error(`  ${size} lines done`);
}

// Find references to lib:f from its declaration. The first request analyzes the whole workspace,
// later ones read the symbol index.
{
    const uri = pathToFileURL(join(workDir, "workspace", "lib.jqm")).href;
    const opened = client.nextDiagnostics(uri);
    client.open(uri, LIBRARY_TEXT);
    await opened;
    const params = {
        textDocument: { uri },
        position: { line: 1, character: "declare function lib:".length + 1 },
        context: { includeDeclaration: false },
    };
    const timeReferences = async () => {
        const start = performance.now();
        const found = await client.request("textDocument/references", params);
        return { ms: performance.now() - start, count: found?.length ?? 0 };
    };
    const first = await timeReferences();
    let count = 0;
    const later = await repeat(async () => {
        const r = await timeReferences();
        count = r.count;
        return r.ms;
    });
    results.references = { files: MAIN_MODULES + 1, expected: 3 * MAIN_MODULES, firstMs: first.ms, firstCount: first.count, count, later };
}

await client.stop();
writeFileSync(outPath, JSON.stringify(results));
process.exit(0);
