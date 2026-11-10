"""Robustness of the tolerances: the reference campaign under alternative drift seeds, and the outcome of
incomplete campaigns, a record-only expert review and non-expert methods on the shipped instance."""
import contextlib, io, json, os, subprocess, sys, time, importlib
import tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
S = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance")); sys.path.insert(0, os.path.join(ROOT, "solution")); sys.path.insert(1, os.path.join(ROOT, "tests"))
import project as P, grade as G, solve as R
import urllib.request

def worst(review, T):
    out = {}
    for u in P.UNITS:
        if T[u]["verdict"] == "undetermined": continue
        a = review["units"][u]
        for k, (kind, tol) in G.TOL.items():
            d = abs(a[k] - T[u][k]) / (tol if kind == "abs" else tol * abs(T[u][k]))
            if d > out.get(k, (0, ""))[0]: out[k] = (d, u)
        if a["verdict"] != T[u]["verdict"]: out.setdefault("verdict", []).append(u)
    return out

class FakeService:
    def __init__(self, budget): self.left = budget; self.done = {}
    def get(self, path):
        if path == "/status": return dict(verifications_remaining=self.left)
        item = path.split("item=")[1]
        if item not in self.done:
            if self.left <= 0: raise RuntimeError("budget")
            self.left -= 1; self.done[item] = P.verification(item)
        return self.done[item]

R.DATA = os.path.join(ROOT, "environment", "data")
PLAN = None
class PlanService(FakeService):
    """Serves the reference's requests, but answers only the items of PLAN(reference plan): the others come
    back as the record room, as if never verified (no charge)."""
    def __init__(self, budget, plan_fn):
        super().__init__(budget); self.plan_fn = plan_fn; self.wanted = []
    def get(self, path):
        if path == "/status" or self.plan_fn is None: return FakeService.get(self, path)
        item = path.split("item=")[1]; self.wanted.append(item.split(":")[1])
        allowed = self.plan_fn(list(REF_PLAN))
        if item.split(":")[1] in allowed: return FakeService.get(self, path)
        s = P.RECORD_BY[item.split(":")[1]]
        return dict(item=item, name=s["name"], level=s["level"], area_m2=s["area"], occupants_current_layout=s["people"],
                    use_category=s["cat"], equipment_nameplate_w=s["equip"], exterior_walls_m2=s["walls"], glazing_m2=s["glass"],
                    glazing_type=s["glz"], roof_m2=s["roof"], roof_assembly=s["roof_assembly"], served_by="new RTU per submittal")
REF_PLAN = ["160", "161", "144", "223", "110", "220", "112"]
def run_ref(plan_fn=None):
    svc = PlanService(P.BUDGET, plan_fn); R.get = svc.get
    R.OUT = os.path.join(S, "review_out" + ".json")
    with contextlib.redirect_stdout(io.StringIO()):  # solve.py prints its campaign
        R.main()
    return json.load(open(R.OUT))

print("drift seeds, reference campaign: worst deviation as a fraction of the tolerance (>1 fails)")
for seed in [0, 1, 2, 3, 4, 5, 6, 7, 8]:
    P.DRIFT_SEED = seed
    T = P.truth()
    rv = run_ref()
    w = worst(rv, T)
    print("seed %d" % seed, "  ".join("%s %.2f(%s)" % (k.replace("_kw","").replace("net_capacity","cap").replace("block","load"), v[0], v[1]) for k, v in w.items() if k != "verdict"),
          "VERDICT " + str(w["verdict"]) if "verdict" in w else "")
P.DRIFT_SEED = 0

print("\ncampaign variants on the shipped instance (pass/fail, worst field)")
T = P.truth()
cases = {
    "reference": lambda p: p,
    "no verification (record + records only)": lambda p: [],
    "skip the lab rooms": lambda p: [x for x in p if x not in ("160", "161")],
    "skip 112 (14 m2 office class)": lambda p: [x for x in p if x != "112"],
    "skip 220 (16 m2 office class)": lambda p: [x for x in p if x != "220"],
    "skip 223 (mid office class)": lambda p: [x for x in p if x != "223"],
    "skip 144 (conference class)": lambda p: [x for x in p if x != "144"],
    "skip 110 (open office class)": lambda p: [x for x in p if x != "110"],
    "largest rooms (110, 160, 223, 144; no 112, 220, 161)": lambda p: ["110", "160", "223", "144"],
}
for name, f in cases.items():
    rv = run_ref(f)
    w = worst(rv, T)
    bad = {k: v for k, v in w.items() if k != "verdict" and v[0] > 1}
    ok = not bad and "verdict" not in w
    print("%-42s %s  %s" % (name, "PASS" if ok else "FAIL", ", ".join("%s %.1fx(%s)" % (k, v[0], v[1]) for k, v in sorted(bad.items(), key=lambda kv: -kv[1][0])[:3]) + (" verdict " + str(w["verdict"]) if "verdict" in w else "")))
