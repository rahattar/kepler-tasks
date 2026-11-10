"""The reference solution, solution/solve.py, against the District's review on the shipped instance. solve.py reads
only the shipped files and the service's reports, and shares no code with the sealed method (method.py,
project_base.py, project.py): it is the independent implementation of the standard's method. The service is
simulated in-process from the sealed definition, with the same budget, so the run needs no container.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import contextlib, io, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests")); sys.path.insert(1, os.path.join(ROOT, "solution"))
import project as P, grade as G, solve as R


class Service:
    def __init__(self):
        self.left = P.BUDGET; self.done = {}
    def get(self, path):
        if path == "/status":
            return dict(verifications_remaining=self.left)
        item = path.split("item=")[1]
        if item not in self.done:
            if self.left <= 0:
                raise RuntimeError("budget spent")
            self.left -= 1; self.done[item] = P.verification(item)
        return self.done[item]


if __name__ == "__main__":
    svc = Service(); R.get = svc.get
    R.DATA = os.path.join(ROOT, "environment", "data")
    R.OUT = os.path.join(tempfile.mkdtemp(), "review.json")
    with contextlib.redirect_stdout(io.StringIO()):  # solve.py prints its campaign
        R.main()
    T = P.truth(); rv = json.load(open(R.OUT)); g = G.grade(R.OUT)
    print("reference solution vs the District's review, shipped instance")
    print("verifications used: %d of %d (%s)" % (P.BUDGET - svc.left, P.BUDGET, ", ".join(sorted(svc.done))))
    print("%-6s %-18s %-18s %s" % ("unit", "verdict", "District", "deviation per quantity (percent; EWB in K)"))
    worst = 0.0
    for u in P.UNITS:
        a, t = rv["units"][u], T[u]
        if t["verdict"] == "undetermined":
            print("%-6s %-18s %-18s missing %s (District %s)" % (u, a["verdict"], t["verdict"], a.get("missing"), t["missing"]))
            continue
        parts = []
        for k, (kind, tol) in G.TOL.items():
            d = a[k] - t[k] if kind == "abs" else 100 * (a[k] / t[k] - 1)
            worst = max(worst, abs(a[k] - t[k]) / (tol if kind == "abs" else tol * abs(t[k])))
            parts.append("%s %+.2f" % (k.replace("_kw", "").replace("net_capacity", "cap").replace("block", "load")
                                       .replace("coil_entering_wb_c", "EWB").replace("outdoor_air_l_s", "OA"), d))
        print("%-6s %-18s %-18s %s" % (u, a["verdict"], t["verdict"], "  ".join(parts)))
    print("submittal %s (District %s)" % (rv["submittal"], T["submittal"]))
    print("largest deviation as a fraction of its tolerance: %.2f" % worst)
    print("grade: %s, units wrong %d" % ("PASS" if g["passed"] else "FAIL", len(g["wrong"])))
