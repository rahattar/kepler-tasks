#!/bin/bash
# mk.sh <name>: a probe sandbox at /tmp/<name> from the core, by tools/mkprobe.sh, with the brief filled in
set -e
H=$(cd "$(dirname "$0")" && pwd); S=/tmp/$1
bash "$H/../../tools/mkprobe.sh" "$H/core" "$S"
rm -rf "$S/rig" "$S/app/lab_reports"
sed "s#PROBE#$S#g" "$H/brief.txt" > "$S/brief.txt"
test -f "$S/app/data/docs/rs4_rope_bending.md" && test -f "$S/app/data/pending/melt_hall/surveys.csv" && test -f "$S/app/data/examples/plate_shop/expected.csv"
echo "$S ready"
