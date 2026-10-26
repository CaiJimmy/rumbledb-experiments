// Summarizes a result of correctness.mjs: false positives on valid queries, and the erroneous queries
// reported, with an error or with a warning (the wrapper reports everything as a warning).
//
// Usage: node analyze-correctness.mjs <correctness.json> [-v]      (-v lists the files)
import { readFileSync } from "node:fs";
import { ANALYZER_ERROR_CODES, isEvaluated } from "./test-queries.mjs";

const data = JSON.parse(readFileSync(process.argv[2], "utf8"));
const results = data.results.filter(isEvaluated);
const valid = results.filter((r) => r.set === "valid");
const erroneous = results.filter((r) => r.set === "erroneous");

const count = (xs, key) => {
    const counts = {};
    for (const x of xs) counts[key(x)] = (counts[key(x)] ?? 0) + 1;
    return counts;
};
const falsePositives = valid.filter((r) => r.diagnostics.length > 0);
const reported = (r) => r.diagnostics.length > 0 || r.warnings.length > 0;

// The analyzer's own codes, mapped to the codes of the specification by their meaning.
const ANALYZER_CODES = { "unresolved-variable": "XPST0008", "unresolved-function": "XPST0017", "undefined-namespace-prefix": "XPST0081" };
const specCode = (d) => (d.source === "parser" ? "XPST0003" : (ANALYZER_CODES[d.code] ?? d.code));
const hasExpectedCode = (r) => [...r.diagnostics, ...r.warnings].some((d) => specCode(d) === r.expectation.code);

console.log("timed out:", results.filter((r) => r.timedOut).length);
console.log("valid files:", valid.length, count(valid, (r) => (r.file.endsWith(".xq") ? "xq" : "jq")));
console.log("valid with error diagnostics:", falsePositives.length);
console.log("valid with warnings:", valid.filter((r) => r.warnings.length > 0).length);
console.log(" false positives by code:", count(falsePositives.flatMap((r) => r.diagnostics), (d) => d.code));
console.log("erroneous files:", erroneous.length, count(erroneous, (r) => r.expectation.code));
console.log("erroneous reported (error or warning):", erroneous.filter(reported).length);
console.log(" ... with the expected code:", erroneous.filter(hasExpectedCode).length);
for (const code of ANALYZER_ERROR_CODES) {
    const withCode = erroneous.filter((r) => r.expectation.code === code);
    console.log(` ${code}: ${withCode.filter(reported).length}/${withCode.length}`);
}

if (process.argv[3] === "-v") {
    console.log("\n--- false positives");
    for (const r of falsePositives) console.log(r.file, "|", r.diagnostics.map((d) => `${d.code}: ${d.message}`).join(" ;; ").slice(0, 220));
    console.log("\n--- missed");
    for (const r of erroneous.filter((r) => !reported(r))) console.log(r.file, r.expectation.code);
}
