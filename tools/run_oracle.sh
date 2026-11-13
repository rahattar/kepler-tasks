#!/bin/bash
# Runs a bundle's oracle in Docker on this machine, the way intake does: solve.sh in the agent's image, the
# declared artifact carried over, test.sh in the verifier's image with no network.
#
#   tools/run_oracle.sh <bundle.zip> [--root]
#
# --root runs solve.sh as root instead of the user task.toml names for the agent. Needs Docker and unzip.
# Prints solve.sh's and test.sh's output, the reward, and whatever the verifier left in /logs/verifier.
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: $0 <bundle.zip> [--root]"; exit 2; }
zip="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
as_root="${2:-}"
work="$(mktemp -d)"
unzip -q "$zip" -d "$work/bundle"
cd "$work/bundle"

artifact="$(sed -n 's/^artifacts = \["\(.*\)"\]$/\1/p' task.toml)"
user="$(sed -n '/^\[agent\]/,/^\[/s/^user = "\(.*\)"$/\1/p' task.toml)"
[ "$as_root" = "--root" ] && user=root
[ -n "$artifact" ] || { echo "task.toml declares no artifact"; exit 2; }
tag="oracle-$$"
echo "== building the two images (the first build downloads the base image and the pinned packages)"
docker build -q -t "$tag-env" environment
docker build -q -t "$tag-tests" tests

echo "== solve.sh in the agent's image, as ${user:-root}"
agent="$(docker create ${user:+--user "$user"} --cpus 2 --memory 4g "$tag-env" bash /solution/solve.sh)"
docker cp solution "$agent":/solution
docker start -a "$agent" || echo "solve.sh ended with a status other than 0"
if ! docker cp "$agent":"$artifact" "$work/artifact"; then
    echo "solve.sh left nothing at $artifact"
    docker rm -f "$agent" > /dev/null
    exit 1
fi
docker rm -f "$agent" > /dev/null

echo "== test.sh in the verifier's image, no network"
verifier="$(docker create --network none --cpus 2 --memory 4g "$tag-tests" bash /tests/test.sh)"
docker cp "$work/artifact" "$verifier":"$artifact"
begun=$(date +%s)
docker start -a "$verifier" || true
took=$(( $(date +%s) - begun ))
docker cp "$verifier":/logs/verifier "$work/logs" || true
docker rm -f "$verifier" > /dev/null
docker rmi -f "$tag-env" "$tag-tests" > /dev/null

echo
echo "== reward: $(cat "$work/logs/reward.txt" 2>/dev/null || echo 'no reward file') (the oracle needs 1), verifier ${took} s"
for left in "$work"/logs/*.json; do
    [ -f "$left" ] || continue
    case "$(basename "$left")" in ctrf.json) continue ;; esac
    echo "-- $(basename "$left")"
    cat "$left"
    echo
done
echo "kept: $work/logs"
