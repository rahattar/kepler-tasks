#!/bin/bash
# gradeprobe.sh BUNDLE DIR...: grades each probe's sheet with the task's own grader, and reports the order it
# placed. Run from the repository root.
set -u
B=$1; shift
for D in "$@"; do
    name=$(basename "$D")
    sheet="$D/app/output/diagnosis.csv"
    echo "===================== $name"
    if [ -f "$D/rig/state/state.json" ]; then
        python3 -c "
import json,sys
s=json.load(open('$D/rig/state/state.json'))
print('order: ' + ', '.join('%s %s' % (t['chamber'], t['test']) for t in s.get('tests', [])) or 'order: none')
" 2>/dev/null || echo "order: unreadable"
    else
        echo "order: none placed"
    fi
    if [ -f "$sheet" ]; then
        python3 -I "$B/tests/grade_audit.py" "$sheet"
    else
        echo "no sheet written"
    fi
done
