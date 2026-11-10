#!/bin/bash
# Runs the reference solution end to end against a live bench service, exactly as it
# will run in the task: the bench in its own process holding the sealed parameters, the
# reference reaching it only through the client, under the real budget.
#
#   bash run_reference.sh            # writes the recipe to $OUT/app/recipe.json
#   PORT=9001 OUT=/tmp/myrun bash run_reference.sh
#
# Every path resolves from this script's own location, so the bundle can live anywhere.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PORT=${PORT:-8077}
OUT=${OUT:-/tmp/refrun}
PIDFILE="$OUT/bench.pid"

rm -rf "$OUT" && mkdir -p "$OUT/app" "$OUT/client"

cd "$ROOT/environment/bench" || exit 1
BENCH_PORT=$PORT python3 server.py > "$OUT/bench_server.log" 2>&1 &
echo $! > "$PIDFILE"

# Wait for the service rather than sleeping a fixed time: a slow bind used to look
# like a solver failure.
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$PORT/status" > /dev/null 2>&1; then break; fi
  sleep 1
done

cp "$ROOT/environment/bench.py" "$OUT/client/bench.py"

cd "$OUT" || exit 1
BENCH_URL="http://127.0.0.1:$PORT" \
CHILL_DATA="$ROOT/environment/data" \
CHILL_RECIPE="$OUT/app/recipe.json" \
CHILL_BENCH="$OUT/client/bench.py" \
  timeout 1200 python3 "$ROOT/solution/solve.py"
RC=$?

kill "$(cat "$PIDFILE")" 2>/dev/null; rm -f "$PIDFILE"
echo "reference exit code: $RC   recipe: $OUT/app/recipe.json"
exit $RC
