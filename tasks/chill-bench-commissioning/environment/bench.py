#!/usr/bin/env python3
"""Chill-station commissioning bench -- client.

Books a test-wafer run on one station and writes the measured trace to ./bench_runs/.
Every run costs one unit of the commissioning budget, the budget is smaller than the
number of stations, and it does not refill.

    bench.py status
    bench.py run --station S03 --pressure 12.0 --seconds 20

A run places an instrumented 300 mm test wafer on the named station, admits backside
helium at the pressure you ask for, and logs mass-mean, inner-zone, outer-zone and
plate-RTD temperature at 10 Hz for as long as you ask for. Test wafers are scrap: a run
is free to sit outside the production spec, that is what the bench is for.

A request the bench refuses -- an unknown station, a pressure outside the supply range,
an impossible run length -- costs no budget.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(os.getcwd(), "bench_runs")
BENCH = os.environ.get("BENCH_URL", "http://bench:8000")


def _call(path, params=None):
    url = BENCH.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": f"bench returned HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"error": f"cannot reach the bench at {BENCH}: {e.reason}"}


def cmd_status(_):
    s = _call("/status")
    if "error" in s:
        print("ERROR:", s["error"], file=sys.stderr)
        return 1
    print(f"commissioning budget: {s['runs_used']} of {s['budget_total']} runs used, "
          f"{s['runs_remaining']} remaining")
    print(f"stations on this bench: {', '.join(s['stations'])}")
    print(f"maximum run length: {s['max_run_s']:g} s")
    if s["runs"]:
        print("\n  #  station  pressure  length")
        for r in s["runs"]:
            print("  %-2d %-7s  %6.2f    %5.1f"
                  % (r["index"], r["station"], r["pressure_torr"], r["seconds"]))
    return 0


def cmd_run(a):
    r = _call("/run", {"station": a.station, "pressure": a.pressure,
                       "seconds": a.seconds})
    if "error" in r:
        print("REFUSED:", r["error"], file=sys.stderr)
        if r.get("budget_charged") is False:
            print("(this request cost no budget)", file=sys.stderr)
        return 2
    os.makedirs(RUNS, exist_ok=True)
    fname = f"run{r['index']:02d}_{a.station}_{a.pressure:g}torr.csv"
    with open(os.path.join(RUNS, fname), "w") as f:
        f.write(r["csv"])
    print(f"run {r['index']}: {a.station} at {a.pressure:g} Torr for {a.seconds:g} s")
    print(f"  wrote bench_runs/{fname}  ({r['samples']} samples)")
    print(f"  budget remaining: {r['runs_remaining']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="budget remaining and runs booked so far")
    r = sub.add_parser("run", help="book one test-wafer run")
    r.add_argument("--station", required=True)
    r.add_argument("--pressure", type=float, required=True, help="helium, Torr")
    r.add_argument("--seconds", type=float, required=True, help="run length")
    a = ap.parse_args()
    return {"status": cmd_status, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
