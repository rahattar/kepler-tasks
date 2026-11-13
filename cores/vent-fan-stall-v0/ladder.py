"""ladder.py MODE PACKAGE_DIR OUT_CSV: programs that stop short of following the district through its log.

  free          every survey round solved by itself from a standing start (fans guessed healthy)
  free_low      the same from a start with every fan at a tenth of free delivery
  survey_warm   every survey round solved from the round before it
  event_newton  every log entry solved in order, one Newton solve from the state before it
  event_flow    every log entry in order, the change made at once and the flow left to settle
"""
import csv, sys
import numpy as np
from ref_airflow import District

def run(mode, folder, out):
    d = District(folder)
    def cold(frac):
        q = np.ones(d.B); p = np.zeros(d.N)
        for j, qs, ps, qt, qp in d.fans: q[j] = frac * qs[-1]
        return q, p
    def solve(q, p):
        q1, p1, ok = d.newton(q, p, d.R)
        if not ok: q1, p1 = d.settle(q, p, d.R)
        return q1, p1
    rounds = sorted({t for _, t, _ in d.points}); at = {}
    seq = sorted([(t, 0, x, v) for t, x, v in d.events] + [(t, 1, None, None) for t in rounds])
    q, p = solve(*cold(0.75))
    for t, kind, x, v in seq:
        if kind == 0:
            j = d.item_branch[x]; d.R[j] = d.res(x, v)
            if mode == "event_newton": q, p = solve(q, p)
            elif mode == "event_flow": q, p = d.settle(q, p, d.R)
        else:
            if mode == "free": q, p = solve(*cold(0.75))
            elif mode == "free_low": q, p = solve(*cold(0.10))
            elif mode == "survey_warm": q, p = solve(q, p)
            at[t] = q.copy()
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["point", "flow_m3_s"])
        for pt, t, j in d.points: w.writerow([pt, "%.4f" % at[t][j]])

if __name__ == "__main__":
    run(*sys.argv[1:4])
