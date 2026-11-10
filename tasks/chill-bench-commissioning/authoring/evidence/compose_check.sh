#!/bin/bash
# Brings the environment up as real containers and checks the things that only a
# container run can check:
#
#   1. docker compose parses the shipped file and starts both services
#   2. the agent service resolves the bench by its service NAME over the compose network
#   3. the sealed fleet parameters are absent from the agent container
#   4. the budget is enforced across that network boundary and cannot be reset from the
#      agent side
#   5. solve.sh runs inside the agent container and produces a recipe
#
# The base image is swapped for a locally built one because this sandbox cannot reach
# Docker Hub. Everything else -- the compose file's structure, service names, the
# network hop, the client, the server -- is exactly what ships.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK=/tmp/composetest
PROJ=chillbench

rm -rf "$WORK" && mkdir -p "$WORK"
cp -r "$ROOT/environment" "$WORK/environment"
cp -r "$ROOT/solution" "$WORK/solution"

# swap only the base image and the package installs; the rest of each Dockerfile stands
python3 - "$WORK" <<'PY'
import re, sys, os
w = sys.argv[1]
for df in (f"{w}/environment/Dockerfile", f"{w}/environment/bench/Dockerfile"):
    s = open(df).read()
    s = re.sub(r"^FROM .*$", "FROM localbase:latest", s, count=1, flags=re.M)
    s = re.sub(r"RUN apt-get update[\s\S]*?rm -rf /var/lib/apt/lists/\*\n", "", s)
    s = re.sub(r"RUN pip install[\s\S]*?\n\n", "\n", s)
    open(df, "w").write(s)
PY

cd "$WORK/environment"
echo "=== 1. compose up ==="
docker compose -p "$PROJ" up -d --build 2>&1 | tail -6 || exit 1
sleep 6
docker compose -p "$PROJ" ps --format '  {{.Service}}  {{.State}}'

A() { docker compose -p "$PROJ" exec -T default "$@"; }

echo
echo "=== 2. agent reaches the bench by service name ==="
A python3 /app/bench.py status || exit 1

echo
echo "=== 3. is anything sealed visible from the agent container? ==="
echo -n "  make_fleet.py present: "; A sh -c 'find / -name make_fleet.py 2>/dev/null | head -1' | grep -q . && echo "LEAK" || echo "no"
echo -n "  bench_core.py present: "; A sh -c 'find / -name bench_core.py 2>/dev/null | head -1' | grep -q . && echo "LEAK" || echo "no"
echo -n "  physics.py present   : "; A sh -c 'find / -name physics.py 2>/dev/null | head -1' | grep -q . && echo "LEAK" || echo "no"
echo -n "  _alpha in /data      : "; A sh -c 'grep -rl _alpha /data 2>/dev/null | head -1' | grep -q . && echo "LEAK" || echo "no"

echo
echo "=== 4. budget is enforced server side ==="
for i in 1 2 3 4 5 6 7 8; do
  A python3 /app/bench.py run --station "S0${i}" --pressure 12 --seconds 6 > /dev/null 2>&1
done
echo -n "  after 8 runs: "; A python3 /app/bench.py status | head -1
echo "  a 9th run:"
A python3 /app/bench.py run --station S09 --pressure 12 --seconds 6 2>&1 | sed 's/^/    /'
echo "  deleting the agent-side run log and asking again:"
A sh -c 'rm -rf /app/bench_runs' 2>/dev/null
A python3 /app/bench.py run --station S09 --pressure 12 --seconds 6 2>&1 | sed 's/^/    /'
echo -n "  budget after the reset attempt: "; A python3 /app/bench.py status | head -1

echo
echo "=== 5. tear down, bring up clean, run the reference ==="
docker compose -p "$PROJ" down -v > /dev/null 2>&1
docker compose -p "$PROJ" up -d --build 2>&1 | tail -2
sleep 6
docker cp "$WORK/solution/solve.py" "$(docker compose -p $PROJ ps -q default)":/app/solve.py
docker cp "$WORK/solution/solve.sh" "$(docker compose -p $PROJ ps -q default)":/app/solve.sh
A sh -c 'cd /app && CHILL_DATA=/data CHILL_RECIPE=/app/recipe.json CHILL_BENCH=/app/bench.py python3 /app/solve.py' 2>&1 | tail -16
docker cp "$(docker compose -p $PROJ ps -q default)":/app/recipe.json /tmp/compose_recipe.json 2>/dev/null \
  && echo "  recipe copied out for grading" || echo "  NO RECIPE PRODUCED"

docker compose -p "$PROJ" down -v > /dev/null 2>&1
echo "  stack torn down"
