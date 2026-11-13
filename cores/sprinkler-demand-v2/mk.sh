#!/bin/bash
# mk.sh PROBE_DIR : a probe sandbox with the agent-visible data only
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
P=$1
rm -rf "$P"; mkdir -p "$P/app/data" "$P/app/output" "$P/app/work"
cp -r "$HERE/core/data/docs" "$HERE/core/data/examples" "$HERE/core/data/pending" "$P/app/data/"
sed "s#PROBE#$P#g" "$HERE/brief.txt" > "$P/brief.txt"
