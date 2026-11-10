#!/bin/bash
# mkprobe-vacwork.sh BUNDLE DIR: a local copy of the agent environment of a bundle whose rig is a submit-once
# order program (base-pressure-diagnosis and anything built like it), for probe agents.
#
# DIR/app stands for /app: data, output, DIR/app/vacwork for the reports and a scratch directory, plus the
# order command DIR/app/vacwork-run (named apart from the reports directory, which the real image keeps at /app/vacwork).
# The order program and the sealed definition sit in DIR/rig, which the probe must not read. The order state lives
# in DIR/rig/state, so the budget does not refill when the probe retries.
set -e
B=$1; D=$2; PY=${PY:-python3}
rm -rf "$D"; mkdir -p "$D/app/output" "$D/app/vacwork" "$D/app/work" "$D/rig/state" "$D/rig/sealed"
cp -r "$B/environment/data" "$D/app/data"
cp "$B/environment/rig/vacwork.py" "$D/rig/vacwork.py"
cp "$B/environment/rig/sealed/"* "$D/rig/sealed/"
chmod 700 "$D/rig/sealed" "$D/rig/state"
chmod 755 "$D/app/vacwork"
printf '#!/bin/bash\ncase "${1:-}" in\n  status|submit) exec %s -B %s/rig/vacwork.py "$1" %s/app/vacwork %s/rig/state/state.json ;;\n  *) echo "usage: vacwork status | vacwork submit < plan.json" >&2; exit 2 ;;\nesac\n' \
  "$PY" "$D" "$D" "$D" > "$D/app/vacwork-run"
chmod 755 "$D/app/vacwork-run"
echo "sandbox ready at $D"
