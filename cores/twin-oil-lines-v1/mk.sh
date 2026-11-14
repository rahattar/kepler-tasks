#!/bin/bash
# mk.sh <label> [limit_s]: a probe sandbox at /tmp/ol1_<label>, built by tools/mkprobe.sh from core/, the crew's
# command at app/heatsurvey answering for the two example sites only, the brief beside it
set -e
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
S=/tmp/ol1_$1; LIMIT=${2:-60}
bash "$REPO/tools/mkprobe.sh" "$HERE/core" "$S" "" heatsurvey >/dev/null
rmdir "$S/app/lab_reports" 2>/dev/null || true
sed -e "s#PROBE#$S#g" -e "s#LIMIT#$LIMIT#g" "$HERE/brief.txt" > "$S/brief.txt"
chmod -R a-w "$S/app/data"
echo "$S ready"
