#!/bin/bash
# mk.sh NAME LIMIT: a probe sandbox at /tmp/NAME from this core's agent data, brief at /tmp/NAME/brief.txt
set -e
here=$(cd "$(dirname "$0")" && pwd); box=/tmp/$1
bash "$here/../../tools/mkprobe.sh" "$here/core" "$box" > /dev/null
rm -rf "$box/rig" "$box/app/lab_reports"
sed -e "s#PROBE#$box#g" -e "s#LIMIT#$2#g" "$here/brief.txt" > "$box/brief.txt"
for f in docs/pw5_ratchet.md docs/line_package.md examples/kiln_row/expected.csv pending/steam_header/history.csv; do
  test -f "$box/app/data/$f" || { echo "mk.sh: $f missing" >&2; exit 1; }
done
test ! -e "$box/app/data/pending/steam_header/expected.csv"
echo "$box ready"
