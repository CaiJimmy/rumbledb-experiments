#!/usr/bin/env bash
# Builds one RumbleDB fat jar per version listed in an experiment's versions.csv, into <experiment>/jars.
# Usage: benchkit/build.sh EXPERIMENT_DIR [path to RumbleDB repository] [names]
#   (repository default: ../rumble next to experiments/; names: comma-separated versions, default all)
# Needs Maven and JDK 17. The sources of each commit are extracted into <experiment>/build/<name>, and the
# Maven output goes to <experiment>/build/<name>.log.
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
EXPERIMENT="$(cd "$1" && pwd)"
REPO="$(cd "${2:-$KIT/../../rumble}" && pwd)"
ONLY="${3:-}"
mkdir -p "$EXPERIMENT/jars" "$EXPERIMENT/build"
while IFS=, read -r name commit description; do
  [[ "$name" == "name" || -z "$name" ]] && continue
  [[ -n "$ONLY" && ",$ONLY," != *",$name,"* ]] && continue
  src="$EXPERIMENT/build/$name"
  rm -rf "$src"; mkdir -p "$src"
  # Some test files of RumbleDB have names that start with "._". The tar of macOS treats such files as
  # metadata of other files and does not extract them, unless --no-mac-metadata is given.
  tar_options=(-x)
  if [[ "$(uname -s)" == Darwin ]]; then
    tar_options+=(--no-mac-metadata)
  fi
  if ! git -C "$REPO" archive "$commit" | tar "${tar_options[@]}" -C "$src"; then
    echo "Could not extract $commit" >&2
    exit 1
  fi
  echo "Building $name ($commit): $description"
  (cd "$src" && mvn -q -DskipTests -Dspotless.check.skip=true -Dspotless.apply.skip=true \
      clean compile assembly:single > "$EXPERIMENT/build/$name.log" 2>&1)
  cp "$src"/target/*-with-dependencies.jar "$EXPERIMENT/jars/$name.jar"
done < "$EXPERIMENT/versions.csv"
echo "Jars in $EXPERIMENT/jars"
