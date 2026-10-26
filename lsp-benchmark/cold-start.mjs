// Cold start of the language server: each round starts a new server process, opens a short valid
// query and waits for its first diagnostics, then edits it once more. With the wrapper, the first
// type check also starts the wrapper's JVM. A second query reads a Parquet file, whose schema
// RumbleDB infers through Spark at compile time; it shows the cost of starting Spark on first use.
//
// Usage: node cold-start.mjs <on|off> <out.json>      Environment: ROUNDS (default 5)
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { LspClient, parseArgs } from "./lsp-client.mjs";

const { wrapper, outPath } = parseArgs("cold-start.mjs");
const ROUNDS = Number(process.env.ROUNDS ?? 5);

const QUERY = `let $orders := [ { "id": 1, "total": 12.5 }, { "id": 2, "total": 30 } ]
for $o in $orders[]
where $o.total gt 20
return { "id": $o.id, "total": $o.total }
`;
const PARQUET = join(import.meta.dirname, "..", "..", "rumble", "src", "test", "resources", "queries", "sample-json.snappy.parquet");
const SPARK_QUERY = `for $row in parquet-file("${PARQUET}") where $row.a gt 1 return $row\n`;

const workDir = join(import.meta.dirname, "data", "work", `cold-${wrapper ? "on" : "off"}`);
const rounds = [];

for (let round = 0; round < ROUNDS; round++) {
    rmSync(workDir, { recursive: true, force: true });
    mkdirSync(workDir, { recursive: true });

    const launched = performance.now();
    const client = new LspClient({ rootPath: workDir, wrapper, cwd: join(workDir, "server-cwd") });
    await client.start();
    const initializeMs = performance.now() - launched;

    const timeDiagnostics = async (uri, text, open) => {
        const published = client.nextDiagnostics(uri);
        const start = performance.now();
        if (open) client.open(uri, text);
        else client.change(uri, text);
        const diagnostics = await published;
        return { ms: performance.now() - start, count: diagnostics?.length ?? -1 };
    };

    const uri = pathToFileURL(join(workDir, "query.jq")).href;
    const first = await timeDiagnostics(uri, QUERY, true);
    const second = await timeDiagnostics(uri, QUERY.replace("20", "21"), false);
    const sparkUri = pathToFileURL(join(workDir, "spark.jq")).href;
    const sparkFirst = await timeDiagnostics(sparkUri, SPARK_QUERY, true);
    const sparkSecond = await timeDiagnostics(sparkUri, SPARK_QUERY.replace("gt 1", "gt 2"), false);

    await client.stop();
    rounds.push({ initializeMs, first, second, sparkFirst, sparkSecond });
    console.error(`round ${round + 1}: initialize ${initializeMs.toFixed(0)} ms, first ${first.ms.toFixed(0)} ms, ` +
        `second ${second.ms.toFixed(1)} ms, Spark first ${sparkFirst.ms.toFixed(0)} ms, Spark second ${sparkSecond.ms.toFixed(1)} ms`);
    await new Promise((r) => setTimeout(r, 3000)); // let the previous JVM exit
}

writeFileSync(outPath, JSON.stringify({ wrapper, rounds }));
process.exit(0);
