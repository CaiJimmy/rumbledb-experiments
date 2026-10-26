// Correctness: diagnostics of the language server on RumbleDB's own test queries, compared with the
// expectation in each file's header. Analyze the output with analyze-correctness.mjs.
//
// Usage: node correctness.mjs <on|off> <out.json>      (on/off: RumbleDB wrapper)
import { readFileSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { pathToFileURL } from "node:url";
import { LspClient, parseArgs } from "./lsp-client.mjs";
import { ANALYZER_ERROR_CODES, TEST_FILES as ROOT, expectation, runnerLanguage, walk } from "./test-queries.mjs";

const { wrapper, outPath } = parseArgs("correctness.mjs");

const summarize = (d) => ({ code: d.code ?? null, source: d.source ?? null, message: d.message, line: d.range.start.line });
const isError = (d) => d.severity === undefined || d.severity === 1;

const files = walk(ROOT).sort();
const client = new LspClient({ rootPath: ROOT, wrapper });
await client.start();

const results = [];
let n = 0;
for (const file of files) {
    const text = readFileSync(file, "utf8");
    const exp = expectation(text);
    if (!exp) continue;
    // RumbleDB's test runner runs every file as a main module, so it expects XPST0003 for library modules,
    // which are valid on their own.
    const libraryModule = /^\s*module\s+namespace\b/m.test(text.replace(/\(:[\s\S]*?:\)/, ""));
    const valid = exp.kind === "ShouldRun" || exp.kind === "ShouldCompile" || libraryModule;
    const targeted = ANALYZER_ERROR_CODES.includes(exp.code);
    if (!valid && !targeted) continue;

    const uri = pathToFileURL(file).href;
    const wait = client.nextDiagnostics(uri);
    const t0 = performance.now();
    client.open(uri, text, runnerLanguage(relative(ROOT, file)));
    const diagnostics = await wait;
    const ms = performance.now() - t0;
    client.close(uri);

    results.push({
        file: relative(ROOT, file),
        expectation: exp,
        set: valid ? "valid" : "erroneous",
        libraryModule,
        timedOut: diagnostics === null,
        ms,
        diagnostics: (diagnostics ?? []).filter(isError).map(summarize),
        warnings: (diagnostics ?? []).filter((d) => !isError(d)).map(summarize),
    });
    if (++n % 200 === 0) console.error(`${n} files`);
}
await client.stop();
writeFileSync(outPath, JSON.stringify({ wrapper, results }, null, 1));
console.error(`done: ${results.length} files`);
process.exit(0);
