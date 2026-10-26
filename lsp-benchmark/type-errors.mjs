// Type errors: the tests of RumbleDB's static-typing folder that expect an error. RumbleDB's
// StaticTypeTests runs them with static typing enabled, so the wrapper's type check should report them.
// Tests whose error can only occur at run time are left out (test-queries.mjs).
//
// Usage: node type-errors.mjs <on|off> <out.json>
import { readFileSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { pathToFileURL } from "node:url";
import { LspClient, parseArgs } from "./lsp-client.mjs";
import { RUN_TIME_ERROR_TESTS, TEST_FILES as ROOT, expectation, runnerLanguage, walk } from "./test-queries.mjs";

const FOLDER = join(ROOT, "static-typing");
const { wrapper, outPath } = parseArgs("type-errors.mjs");

const tests = walk(FOLDER)
    .sort()
    .map((path) => ({ path, file: relative(ROOT, path), text: readFileSync(path, "utf8") }))
    .map((t) => ({ ...t, exp: expectation(t.text) }))
    .filter((t) => t.exp?.kind === "ShouldCrash" && t.exp.code !== null && !RUN_TIME_ERROR_TESTS.has(t.file));

const client = new LspClient({ rootPath: ROOT, wrapper });
await client.start();

const results = [];
for (const t of tests) {
    const uri = pathToFileURL(t.path).href;
    const published = client.nextDiagnostics(uri);
    client.open(uri, t.text, runnerLanguage(t.file));
    const diagnostics = (await published) ?? [];
    client.close(uri);
    results.push({
        file: t.file,
        expected: t.exp.code,
        diagnostics: diagnostics.map((d) => ({ severity: d.severity, code: d.code ?? null, source: d.source ?? null, message: d.message })),
    });
}

await client.stop();
writeFileSync(outPath, JSON.stringify({ wrapper, results }, null, 1));
console.error(`done: ${results.length} tests`);
process.exit(0);
