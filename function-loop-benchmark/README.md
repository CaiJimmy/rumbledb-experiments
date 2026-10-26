# Function calls: one call site in a loop

This complements `../function-call-benchmark`. In the recursive Fibonacci, every call happens at a different
call site. `once` keeps the body of a finished call at its call site for the next call there, so in Fibonacci
it never gets to reuse anything. Here, a single call site is called n times in a loop, which gives `once` the
best case.

The versions and jars are the same as in `../function-call-benchmark` (`jars` is a link to its `jars/`, and
`versions.csv` is a copy):

| name    | commit      | how a call works |
|---------|-------------|------------------|
| `copy`  | `44222a9`   | every call deep-copies the function item with Java serialization |
| `once`  | `a23c3c7`   | the body is serialized once, deserialized for a call, and kept at the call site for the next call |
| `plans` | `06814d0`   | runtime plans and cursors |
| `final` | `4c7b372`   | #1942 and #1943: the callee plan is reused, and static calls no longer copy the function |

As in the Fibonacci benchmark, the query only makes static calls, and `plans` against `final` shows all
changes between the two commits, not one PR alone.

## Query

`queries/loop.jq.template`, the same for every version:

```jsoniq
declare function local:f($x as integer, $d as integer) as integer {
  if ($d gt 0) then local:f($x, $d - 1) else $x * 2 + 1
};
sum(for $i in 1 to {n} return local:f($i, 0))
```

The result, n(n + 1) + n, is checked on every run. The cost per call is the time of the whole query divided
by the n calls, so it includes the loop and the body of the function.

The recursive branch of `local:f` is never taken, since `$d` is always 0. It is there to keep RumbleDB from
inlining the function: `FunctionInliningVisitor`, which is on by default, inlines every function that is not
recursive, sequential or exiting, and then no call would be left to measure. On 2026-10-17 I checked with
`--print-iterator-tree` (plus `--log-level DEBUG` for `once` and `plans`) that `copy`, `once` and `plans` all
keep a `StaticUserDefinedFunctionCallIterator` inside the `ReturnClauseIterator`, with every iterator in
`local` execution mode (n = 3).

## Running it

```sh
../function-call-benchmark/build.sh   # if the jars are missing
./run-all-jvm.sh                      # 3 JVMs x (2 warm-up + 5 timed runs), versions interleaved
python3 analyze.py                    # medians and cost per call
```

## Results (2026-10-22)

The run is in `data/jvm/run-2026-10-22T054827Z-12935/`: 3 JVMs per version and n, each with 2 untimed
warm-up runs and 5 timed runs, 12 GB of driver memory. Each cell is the median of the per-JVM medians, then
the spread between the JVMs and the median divided by n:

| n         | `copy`                   | `once`                     | `plans`                  | `final`                    |
|-----------|--------------------------|----------------------------|--------------------------|----------------------------|
| 10,000    | 8.225 s (6%, 822 µs)     | 0.0177 s (15%, 1.8 µs)     | 0.0235 s (22%, 2.4 µs)   | 0.0201 s (10%, 2.0 µs)     |
| 30,000    |                          | 0.0212 s (46%, 0.71 µs)    | 0.0368 s (14%, 1.2 µs)   | 0.0286 s (6%, 0.95 µs)     |
| 100,000   |                          | 0.0411 s (7%, 0.41 µs)     | 0.0878 s (4%, 0.88 µs)   | 0.0447 s (5%, 0.45 µs)     |
| 300,000   |                          | 0.103 s (8%, 0.34 µs)      | 0.247 s (2%, 0.82 µs)    | 0.107 s (9%, 0.36 µs)      |
| 1,000,000 |                          | 0.308 s (3%, **0.31 µs**)  | 0.792 s (5%, **0.79 µs**) | 0.310 s (5%, **0.31 µs**) |

Memory allocated by the query per call, at n = 1,000,000 (and at n = 10,000 in parentheses): `once` 1.40 KB
(1.55 KB), `plans` 3.64 KB (3.76 KB), `final` 1.68 KB (2.32 KB). `copy` allocates 514 KB per call at
n = 10,000. All results are correct. At small n, the fixed cost of the query outweighs the calls.

`plans` builds a new call plan for every call. `final` (#1942, #1943) does not, and it ends up as fast as
`once`, which reuses the iterator tree it kept at the call site. `once` still allocates a bit less, because
`final` creates new cursors for every call.

### Why `copy` stops at 10,000 calls

At n = 30,000, `copy` fails with a `StackOverflowError` in all three JVMs. The logs are in `data/logs/`, from
a run of 2026-10-21 with the same commit; the run above only runs `copy` at n = 10,000.

The cause is in this version's `StaticUserDefinedFunctionCallIterator.closeLocal`, which throws away its
`FunctionItemCallIterator` after every call. The constructor of the next one then wraps the argument
iterators in type-checking iterators, in place, in the argument list it shares with the call site
(`FunctionItemCallIterator.wrapArgumentIteratorsWithTypeCheckingIterators`). So every call at the same call
site adds another layer of `FunctionUntypedAtomicCastIterator` and `AtMostOneItemTypePromotionIterator` around
the argument, and the stack trace shows a long chain of them. The cost per call grows with it. In a quick
check (one JVM, 3 timed runs, not kept here), a call took 540 µs at n = 1,250, 572 µs at 2,500 and 679 µs at
5,000, against 822 µs at 10,000 in the run above.

#1696 (`once`) keeps the call iterator at the call site, so the arguments are wrapped only once. In the
Fibonacci benchmark each call site is used only once, which is why the bug does not show up there.

## Data

| Folder | Contents |
|---|---|
| `data/jvm/` | the run above |
| `data/logs/` | output of the `copy` JVMs that failed at n = 30,000 |
