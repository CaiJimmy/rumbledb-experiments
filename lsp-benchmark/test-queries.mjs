// Which of RumbleDB's test queries the evaluation uses.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

// RumbleDB's test queries, in the RumbleDB repository next to this repository.
export const TEST_FILES = join(import.meta.dirname, "..", "..", "rumble", "src", "test", "resources", "test_files");

/** All test queries (.jq, .xq) under `dir`, as absolute paths. */
export function walk(dir) {
    return readdirSync(dir).flatMap((e) => {
        const p = join(dir, e);
        return statSync(p).isDirectory() ? walk(p) : /\.(jq|xq)$/.test(e) ? [p] : [];
    });
}

/** The expectation in the `(:JIQS: …:)` header of a test query, for example { kind: "ShouldCrash", code: "XPST0008" }. */
export function expectation(text) {
    const m = /\(:JIQS:\s*(\w+)(?:;\s*ErrorCode="(\w+)")?/.exec(text.slice(0, 400));
    return m ? { kind: m[1], code: m[2] ?? null } : null;
}

// Error codes of the erroneous queries in the evaluation: the errors that the analyzer is designed to report
// (syntax errors, undeclared variables, functions and namespace prefixes).
export const ANALYZER_ERROR_CODES = ["XPST0003", "XPST0008", "XPST0017", "XPST0081"];

// Tests whose expectation is wrong: the query is not valid, although RumbleDB's test expects it to compile.
export const INVALID_TESTS = new Set([
    // Only checks that keywords parse as field names; calls count#3 and for#3, which do not exist (XPST0017).
    "runtime/Keywords2.jq",
]);

/**
 * Whether a result of correctness.mjs is in the evaluation. Left out: library modules (RumbleDB's test
 * runner runs them as main modules), queries that declare JSONiq 1.0 (the language server targets
 * JSONiq 3.1 and XQuery 3.0/3.1), and the invalid tests above.
 */
export function isEvaluated(result) {
    if (result.libraryModule || INVALID_TESTS.has(result.file)) return false;
    const header = readFileSync(join(TEST_FILES, result.file), "utf8").slice(0, 300);
    return !/^\s*jsoniq\s+version\s+"1\.0"/m.test(header);
}

// Static-typing tests that expect an error that can only occur at run time, so no static check can find it.
export const RUN_TIME_ERROR_TESTS = new Set([
    // SENR0001: the result cannot be serialized, which happens when it is written out.
    "static-typing/postfix/dynamicfunc3.jq",
]);

// RumbleDB's XQueryTests and BugsXQuery run every file of these folders as XQuery 3.1, whatever its
// extension; the other test classes take the language from the extension.
const XQUERY_FOLDERS = ["xquery-parser/", "bugs-xquery/"];

/** The language in which RumbleDB's test runner runs a test file (path relative to test_files). */
export function runnerLanguage(file) {
    if (XQUERY_FOLDERS.some((folder) => file.startsWith(folder))) return "xquery";
    return /\.(xq|xqm|xqy|xquery)$/.test(file) ? "xquery" : "jsoniq";
}
