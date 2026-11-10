#!/bin/bash
# mkprobe.sh BUNDLE DIR [SEED]: a local copy of the agent environment of a task bundle, for probe agents.
# The lab wrapper (here for a `cte` command; rename for other tasks) sits in DIR/app; the sealed files in DIR/rig.
# Needs a python with the task's pinned packages at $PY (default: python3).
set -e
B=$1; D=$2; SEED=${3:-}; PY=${PY:-python3}
rm -rf $D; mkdir -p $D/app/output $D/app/lab_reports $D/app/work $D/rig/state $D/rig/sealed
cp -r $B/environment/data $D/app/data; cp $B/environment/rig/lab.py $D/rig/lab.py; cp $B/environment/rig/sealed/* $D/rig/sealed/
[ -n "$SEED" ] && echo "{\"seed\": $SEED}" > $D/rig/sealed/seed.json
chmod 700 $D/rig/sealed $D/rig/state; chmod 755 $D/app/lab_reports
printf '#!/bin/bash\nLAB_DIR=%s/rig REPORT_DIR=%s/app/lab_reports exec %s -B %s/rig/lab.py cte "$@"\n' $D $D $PY $D > $D/app/cte; chmod 755 $D/app/cte
