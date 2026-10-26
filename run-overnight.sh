#!/usr/bin/env bash
# Runs every benchmark of the thesis, one after another (about 9 hours), and writes their console output to
# run-overnight-<UTC time>-<pid>.log. Build the jars first (./build.sh in each benchmark). Every benchmark writes its own
# data/<mode>/run-<UTC time>-<pid>/; a failed script is reported, and the next one still runs.
set -uo pipefail
cd "$(dirname "$0")"
# spark-submit runs the JVM of JAVA_HOME, and the results were measured with Java 17.
if [[ -z "${JAVA_HOME:-}" ]] || ! "$JAVA_HOME/bin/java" -version 2>&1 | grep -q 'version "17'; then
  echo "Set JAVA_HOME to a Java 17 JDK (now: ${JAVA_HOME:-not set})." >&2
  exit 1
fi
LOG="$PWD/run-overnight-$(date -u +%Y-%m-%dT%H%M%SZ)-$$.log"
caffeinate -i -w $$ &
failed=()
step() {
  echo "=== $(date '+%F %T') $*" | tee -a "$LOG"
  if "$@" >> "$LOG" 2>&1; then
    echo "=== PASSED: $*" | tee -a "$LOG"
  else
    status=$?
    failed+=("$* (exit code $status)")
    echo "=== FAILED (exit code $status): $*" | tee -a "$LOG"
  fi
}
step map-benchmark/run-all-jvm.sh
step map-benchmark/run-all-retained.sh
step map-date-key-benchmark/run-all-jvm.sh
step map-date-key-benchmark/run-all-retained.sh
step map-merge-benchmark/run-all-jvm.sh
step map-merge-benchmark/run-all-retained.sh
step map-lookup-benchmark/run-all-jvm.sh
step function-call-benchmark/run-all-jvm.sh
step function-call-benchmark/memory/run-heap.sh
step function-loop-benchmark/run-all-jvm.sh
echo "=== $(date '+%F %T') done" | tee -a "$LOG"
if (( ${#failed[@]} )); then
  printf 'Failed stage: %s\n' "${failed[@]}" | tee -a "$LOG"
  exit 1
fi
