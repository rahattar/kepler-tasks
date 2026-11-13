#!/bin/bash
# regenerates every committed study of the bundle, one at a time, in the order the README quotes them
B=/home/claude/work/bundle/engine-indicating-analysis
export PYTHONDONTWRITEBYTECODE=1
cd "$B/authoring/provenance"
python3 -B manifest.py > /dev/null
python3 -B design_rules.py > ../evidence/design_rules.txt
python3 -B regenerate.py > ../evidence/regenerate.txt
cd $B/authoring/evidence
for s in reference_run route_run slow_run null_run verifier_checks verifier_run seed_screen; do
  python3 -B $s.py > $s.txt 2> /tmp/evidence_$s.err
  echo "$s done $(date +%H:%M:%S) exit $?" >> /tmp/evidence_progress.log
done
find $B -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
echo "all done $(date +%H:%M:%S)" >> /tmp/evidence_progress.log
