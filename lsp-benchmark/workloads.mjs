// Inputs of the latency benchmark: generated JSONiq files of a given length, and a workspace in
// which many main modules call a function of one library module.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

/**
 * A valid JSONiq main module of about `lines` lines, made of functions of five lines. Every function
 * except the first calls the first one, so the depth of calls stays 1 whatever the length.
 * (A chain in which each function calls the previous one overflows the stack of RumbleDB's type
 * checker from about 1,000 functions on, and is not representative of real queries.)
 *
 * The middle function is where the benchmark edits the file:
 * - `digit` replaces the constant added in its first line, an edit that keeps the file valid;
 * - `returnClause` replaces its return clause, to type a completion trigger such as `return $`.
 *
 * Returns the text and the line of the middle function's return clause.
 */
export function generateQuery(lines, { digit = 0, returnClause = null } = {}) {
    const functionCount = Math.max(2, Math.floor(lines / 5));
    const middle = Math.floor(functionCount / 2);
    const out = [];
    for (let i = 0; i < functionCount; i++) {
        const base = i === 0 ? "" : `, "base": [ local:f0($z, $y) ]`;
        const ret = i === middle && returnClause !== null ? returnClause : `return { "id": $z, "name": $s${base} }`;
        out.push(
            `declare function local:f${i}($x as integer, $y as string*) as object* {`,
            `  let $z := $x + ${i === middle ? digit : i}`,
            `  for $s in $y where string-length($s) gt $z`,
            `  ${ret}`,
            `};`,
        );
    }
    out.push(`local:f${functionCount - 1}(1, ("a", "bb", "ccc"))`);
    return { text: out.join("\n") + "\n", returnLine: 5 * middle + 3 };
}

export const LIBRARY_TEXT = `module namespace lib = "lib.jqm";\ndeclare function lib:f($x as integer) as integer { $x + 1 };\n`;

/** Writes a library module `lib.jqm` and `mainModules` main modules that each call `lib:f` three times. */
export function writeReferencesWorkspace(dir, mainModules) {
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "lib.jqm"), LIBRARY_TEXT);
    for (let i = 0; i < mainModules; i++) {
        writeFileSync(
            join(dir, `q${i}.jq`),
            `import module namespace lib = "lib.jqm";\nlet $a := lib:f(${i})\nlet $b := lib:f($a)\nreturn lib:f($b)\n`,
        );
    }
}
