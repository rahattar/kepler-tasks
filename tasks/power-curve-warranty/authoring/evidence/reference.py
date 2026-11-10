"""The reference program (solution/pp12.py) run through tests/grade.py on the six hidden packages, as the verifier
runs it, against the sealed truth; and run as a command on the example against the engineer's reported results.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import csv, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

T = C.truth()
print("Reference program solution/pp12.py, run through tests/grade.py as the verifier runs it (as %s); tolerance %.2f "
      "on the ratio, claim exact, at most %d wrong turbine.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.TOL, C.MAX_WRONG))
out = tempfile.mktemp(suffix=".csv")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
got = {r["turbine"]: r for r in csv.DictReader(open(out))}
rep = {r["turbine"]: r for r in csv.DictReader(open(os.path.join(C.EXAMPLE, "reported_results.csv")))}
print("Example ridgeback-2026h1 against the engineer's reported results (3 decimals):")
print("  worst |ratio - reported| %.4f; claims equal: %s\n" % (
    max(abs(float(got[t]["aep_ratio"]) - float(rep[t]["aep_ratio"])) for t in rep),
    all(got[t]["warranty_claim"] == rep[t]["warranty_claim"] for t in rep)))
r = C.verify(C.REFERENCE)
print("%-22s %-5s %8s %8s %8s %6s %6s" % ("package", "turb", "truth", "ref", "error", "claim", "true"))
worst = 0.0
for p in sorted(T):
    for t in sorted(T[p]):
        x = r["packages"][p]["turbines"][t]
        e = x["aep_ratio"] - T[p][t]["aep_ratio"]; worst = max(worst, abs(e))
        print("%-22s %-5s %8.4f %8.4f %+8.4f %6s %6s" % (p, t, T[p][t]["aep_ratio"], x["aep_ratio"], e,
                                                       x["warranty_claim"], T[p][t]["warranty_claim"]))
claims = sum(v["warranty_claim"] == "yes" for p in T for v in T[p].values())
print("\nturbines %d (claims %d); wrong %d (%s); worst |error| %.4f (%.2f of the tolerance)" % (
    r["turbines"], claims, r["wrong"], "accepted" if r["accepted"] else "rejected", worst, worst / C.TOL))
lo_yes = max(v["aep_ratio"] for p in T for v in T[p].values() if v["warranty_claim"] == "yes")
hi_no = min(v["aep_ratio"] for p in T for v in T[p].values() if v["warranty_claim"] == "no")
print("true ratios: claimed turbines at most %.4f, others at least %.4f (claim threshold 0.97)" % (lo_yes, hi_no))
for p in sorted(T):
    print("  %-22s claims %s" % (p, ", ".join("%s %.4f" % (t, T[p][t]["aep_ratio"]) for t in sorted(T[p]) if T[p][t]["warranty_claim"] == "yes")))
