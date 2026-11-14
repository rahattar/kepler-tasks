#!/bin/bash
# mk.sh <label>: a probe sandbox at /tmp/ol3_<label>: the bundle's environment with TS-2 5.5 and 5.6 stated,
# built by tools/mkprobe.sh, the crew's command at app/heatsurvey answering for the two example sites only
set -e
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
S=/tmp/ol3_$1
bash "$REPO/tools/mkprobe.sh" "$HERE/core" "$S" "" heatsurvey >/dev/null
rmdir "$S/app/lab_reports" 2>/dev/null || true
sed -e "s#PROBE#$S#g" "$HERE/brief.txt" > "$S/brief.txt"
chmod -R a-w "$S/app/data"
echo "$S ready"
