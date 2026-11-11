#!/bin/bash
# mkprobe.sh BUNDLE DIR [SEED] [CMD...]: a local copy of the agent environment of a task bundle, for probe agents.
# The lab wrappers sit in DIR/app, one per command named (default: cte); the sealed files in DIR/rig.
# Needs a python with the task's pinned packages at $PY (default: python3).
set -e
export D
B=$1; D=$2; SEED=${3:-}; shift 3 2>/dev/null || shift $# ; CMDS=${@:-cte}; PY=${PY:-python3}
rm -rf $D; mkdir -p $D/app/output $D/app/lab_reports $D/app/work $D/rig/state $D/rig/sealed
cp -r $B/environment/data $D/app/data
if [ -d $B/environment/rig ]; then
  cp $B/environment/rig/lab.py $D/rig/lab.py; cp $B/environment/rig/sealed/* $D/rig/sealed/
  # keep every key the rig reads; overwriting with one key leaves the laboratory program broken
  [ -n "$SEED" ] && PY=$PY SEED=$SEED python3 -c 'import json,os,sys
p = os.environ["D"] + "/rig/sealed/seed.json"
d = json.load(open(p))
base = int(os.environ["SEED"])
for k in d:
    d[k] = base if k == "seed" else base + 84000
json.dump(d, open(p, "w"))' 
else
  CMDS=""      # a records-only task has no laboratory program
fi
chmod 700 $D/rig/sealed $D/rig/state; chmod 755 $D/app/lab_reports
for c in $CMDS; do
  printf '#!/bin/bash\nLAB_DIR=%s/rig REPORT_DIR=%s/app/lab_reports exec %s -B %s/rig/lab.py %s "$@"\n' $D $D $PY $D $c > $D/app/$c
  chmod 755 $D/app/$c
done

# verify the rig answers before any probe is launched into this sandbox: a usage line, not a traceback
for c in $CMDS; do
  if $D/app/$c 2>&1 | grep -qi traceback; then
    echo "mkprobe: $D/app/$c fails before it does anything" >&2; exit 1
  fi
done
