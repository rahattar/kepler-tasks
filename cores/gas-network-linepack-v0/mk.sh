#!/bin/bash
# mk.sh PROBE_DIR : a probe sandbox with the agent-visible data only; the field team answers for the examples
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
P=$1
rm -rf "$P"; mkdir -p "$P/app/output" "$P/app/work"
cp -r "$HERE/core/data" "$P/app/data"
STATE="/tmp/gascrew_state/$(basename "$P")"
rm -rf "$STATE"
cat > "$P/app/gdsurvey" <<EOW
#!/bin/bash
# gdsurvey PACKAGE_DIR ITEM [ITEM ...]: places the package's one order with the field team
GASCREW_BOOKS="$HERE/crew/dev" GASCREW_STATE="$STATE" exec python3 -B "$HERE/crew/lab.py" gdsurvey "\$@"
EOW
chmod +x "$P/app/gdsurvey"
sed "s#PROBE#$P#g" "$HERE/brief.txt" > "$P/brief.txt"
echo "$P ready"
