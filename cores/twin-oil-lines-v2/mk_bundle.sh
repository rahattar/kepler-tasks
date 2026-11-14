#!/bin/bash
# mk_bundle.sh <label>: a probe sandbox at /tmp/ftl_<label> from the bundle tasks/fuel-transfer-lines, built by
# tools/mkprobe.sh, the crew's command at app/heatsurvey answering for the two example sites only
set -e
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
S=/tmp/ftl_$1
bash "$REPO/tools/mkprobe.sh" "$REPO/tasks/fuel-transfer-lines" "$S" "" heatsurvey >/dev/null
rmdir "$S/app/lab_reports" 2>/dev/null || true
sed -e "s#PROBE#$S#g" "$HERE/brief_bundle.txt" > "$S/brief.txt"
chmod -R a-w "$S/app/data"
echo "$S ready"
