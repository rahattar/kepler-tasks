#!/bin/bash
# perturb.sh NAME 'shell command'  : copy the task, apply the command inside the copy, run preflight, and report
# any FAIL line that the unperturbed baseline does not already have. A check never seen to fail is not known to work.
#   TASK  the task directory (default: ../../tasks/base-pressure-diagnosis next to this script)
#   WORK  a scratch directory (default: /tmp/bpd-perturb)
#   PY    the python to run preflight with (default: python3)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK=${TASK:-$HERE/../../tasks/base-pressure-diagnosis}; WORK=${WORK:-/tmp/bpd-perturb}; PY=${PY:-python3}
name=$1; cmd=$2
mkdir -p $WORK
if [ ! -f $WORK/baseline.txt ]; then
    rm -rf $WORK/base; mkdir -p $WORK/base; cp -r $TASK $WORK/base/base-pressure-diagnosis
    (cd $WORK/base/base-pressure-diagnosis && $PY -B authoring/evidence/preflight.py > $WORK/baseline.txt 2>&1)
fi
d=$WORK/$name; rm -rf $d; mkdir -p $d; cp -r $TASK $d/base-pressure-diagnosis
cd $d/base-pressure-diagnosis && eval "$cmd"
$PY -B authoring/evidence/preflight.py > $d/out.txt 2>&1
new=$(grep '^FAIL' $d/out.txt | grep -v -F -f <(grep '^FAIL' $WORK/baseline.txt | cut -c1-60))
if [ -n "$new" ]; then echo "[$name] CAUGHT: $(echo "$new" | head -3 | tr '\n' '|')"; else echo "[$name] NOT CAUGHT ($(tail -1 $d/out.txt))"; fi
