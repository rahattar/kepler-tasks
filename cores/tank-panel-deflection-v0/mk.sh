#!/bin/bash
# mk.sh <label> [limit_s]: a probe sandbox at /tmp/tp_<label>, built by tools/mkprobe.sh from core/, with the brief beside it
set -e
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
S=/tmp/tp_$1; LIMIT=${2:-60}
bash "$REPO/tools/mkprobe.sh" "$HERE/core" "$S" >/dev/null
sed -e "s#PROBE#$S#g" -e "s#LIMIT#$LIMIT#g" "$HERE/brief.txt" > "$S/brief.txt"
rm -rf "$S/rig" "$S/app/lab_reports"
chmod -R a-w "$S/app/data"
echo "$S ready"
