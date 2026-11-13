#!/bin/bash
# mk.sh <name>: a probe sandbox at /tmp/<name>, built by tools/mkprobe.sh from the core, with the brief filled in
set -e
H=$(cd "$(dirname "$0")" && pwd); S=/tmp/$1
bash "$H/../../tools/mkprobe.sh" "$H/core" "$S"
rm -rf "$S/rig" "$S/app/lab_reports"          # the core has no laboratory
sed "s#PROBE#$S#g" "$H/brief.txt" > "$S/brief.txt"
test -f "$S/app/data/docs/rl2_rod_lift.md" && test -f "$S/app/data/pending/mesa_block/cards.csv" && test -f "$S/app/data/examples/creek_unit/expected.csv"
echo "$S ready"
