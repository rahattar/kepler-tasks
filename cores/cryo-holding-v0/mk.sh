#!/bin/bash
# mk.sh <label> [limit_s]: a probe sandbox at /tmp/cr0_<label>, built by tools/mkprobe.sh from core/, the crew's
# command at app/nertest answering for the two example depots only, the brief beside it
set -e
HERE=$(cd "$(dirname "$0")" && pwd); REPO=/home/claude/kepler-tasks
S=/tmp/cr0_$1; LIMIT=${2:-30}
bash "$REPO/tools/mkprobe.sh" "$HERE/core" "$S" "" nertest >/dev/null
rmdir "$S/app/lab_reports" 2>/dev/null || true
sed -e "s#PROBE#$S#g" -e "s#LIMIT#$LIMIT#g" "$HERE/brief.txt" > "$S/brief.txt"
chmod -R a-w "$S/app/data"
echo "$S ready"
