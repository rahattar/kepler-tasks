#!/bin/bash
# mkprobe.sh BUNDLE DIR [SEED] [CMD...]: a local copy of the agent environment of a task bundle, for probe agents.
# The lab wrappers sit in DIR/app, one per command named (default: cte); the sealed files in DIR/rig.
# Needs a python with the task's pinned packages at $PY (default: python3).
set -e
B=$1; D=$2; SEED=${3:-}; shift 3 2>/dev/null || shift $# ; CMDS=${@:-cte}; PY=${PY:-python3}
rm -rf $D; mkdir -p $D/app/output $D/app/lab_reports $D/app/work $D/rig/state $D/rig/sealed
cp -r $B/environment/data $D/app/data; cp $B/environment/rig/lab.py $D/rig/lab.py; cp $B/environment/rig/sealed/* $D/rig/sealed/
[ -n "$SEED" ] && echo "{\"seed\": $SEED}" > $D/rig/sealed/seed.json
chmod 700 $D/rig/sealed $D/rig/state; chmod 755 $D/app/lab_reports
for c in $CMDS; do
  printf '#!/bin/bash\nLAB_DIR=%s/rig REPORT_DIR=%s/app/lab_reports exec %s -B %s/rig/lab.py %s "$@"\n' $D $D $PY $D $c > $D/app/$c
  chmod 755 $D/app/$c
done
