#!/usr/bin/env bash
# Usage: memory/run.sh VERSION N [INTERVAL, default 15; 0 disables histograms] [MEMORY, default 12g]
# Additional options, including --timeout SECONDS, are passed to run.py.
set -euo pipefail
exec python3 "$(dirname "$0")/run.py" "$@"
