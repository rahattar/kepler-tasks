"""Minimum-zone form (FM-7 section 3) on bore-form-acceptance's RT-1 records under each treatment of the tester's error.

    python3 tools/trap-analysis/check2.py tasks/bore-form-acceptance

Imports the sealed module for its fits and for the truth, which a reviewer may do and an agent cannot. Prints, for
two significance tests (the reference's, and one on the modulus of the mean): which orders a pooled and a split
estimate keep, and each feature's form error as measured, with the pooled estimate removed and with its own state's
removed. Then the least-squares zone against the minimum zone on the true surfaces, the certified scan against the
shop record for the two features every passing booking can scan, and the drawing's tolerances against the sealed
ones. Used for docs/trap-analysis-2026-11-11.md.
"""
import csv, sys, os
import json
import numpy as np
np.seterr(all="ignore")
sys.dont_write_bytecode = True
T = sys.argv[1]
sys.path.insert(0, os.path.join(T, "authoring", "provenance"))
import isim
D = os.path.join(T, "environment", "data")
idx = list(csv.DictReader(open(os.path.join(D, "measurement_index.csv"))))
req = {r["feature"]: (r["form_characteristic"], float(r["form_tolerance_um"])) for r in csv.DictReader(open(os.path.join(D, "drawing_requirements.csv")))}
N = 1800; th = np.arange(N) / N * 2 * np.pi

def secs(path):
    out = {}
    for r in csv.DictReader(open(path)):
        out.setdefault(float(r["section_mm"]), []).append((float(r["angle_deg"]), float(r["radius_mm"])))
    return [np.array(sorted(v))[:, 1] for k, v in sorted(out.items())]

tester = [r for r in idx if "RT-1" in r["instrument"]]
P, M = {}, {}
for r in tester:
    S = secs(os.path.join(D, "measurements", os.path.basename(r["file"])))
    P[r["feature"]] = [isim.assess_profile(th, (s - s.mean()) * 1000.0) for s in S]
    M[r["feature"]] = [s.mean() * 1000.0 for s in S]          # um, room temperature (form does not need 20 C)

def form(f, profs):
    kind = req[f][0]
    if kind == "roundness":
        return max(isim.roundness(th, p) for p in profs)
    bar = sum(M[f]) / 3
    whole = [(M[f][j] - bar) + profs[j] for j in range(3)]
    return isim.cylindricity([th] * 3, whole, [s - 0.5 for s in isim.SECTIONS])

def estimate(feats, test):
    A = np.array([np.mean(P[f], axis=0) for f in feats])
    F = np.fft.rfft(A, axis=1) / N
    e = np.zeros(N); kept = []
    for k in range(2, 120):
        m = F[:, k].mean()
        if test == "reference":       # solution/solve.py: real and imaginary parts each 3 standard errors clear
            sr = F[:, k].real.std(ddof=1) / np.sqrt(len(feats)); si = F[:, k].imag.std(ddof=1) / np.sqrt(len(feats))
            ok = abs(m.real) > 3 * sr and abs(m.imag) > 3 * si
        else:                         # modulus of the mean against the complex scatter
            se = np.sqrt((np.abs(F[:, k] - m) ** 2).sum() / (len(feats) - 1)) / np.sqrt(len(feats))
            ok = abs(m) > 3 * se
        if ok:
            e += 2 * (m.real * np.cos(k * th) - m.imag * np.sin(k * th)); kept.append(k)
    return e, kept

feats = [r["feature"] for r in tester]
before = [r["feature"] for r in tester if r["measured_on"] <= "2026-09-30"]
after = [f for f in feats if f not in before]
for test in ("reference", "modulus"):
    ep, kp = estimate(feats, test); eb, kb = estimate(before, test); ea, ka = estimate(after, test)
    print("test=%s  pooled keeps %s (%.1f um p-v) | before keeps %s (%.1f) | after keeps %s (%.1f)" % (
        test, kp, ep.max() - ep.min(), kb, eb.max() - eb.min(), ka, ea.max() - ea.min()))
    print("  feature char          tol   truth | as measured      | pooled removed   | own state removed")
    wrong = {"raw": [], "pooled": [], "split": []}
    for f in feats:
        t = isim.truth(f); tol = req[f][1]
        e_own = eb if f in before else ea
        vals = {"raw": form(f, P[f]), "pooled": form(f, [p - ep for p in P[f]]), "split": form(f, [p - e_own for p in P[f]])}
        cells = []
        for k in ("raw", "pooled", "split"):
            v = vals[k]; err = v - t["form"]
            flips = (v <= tol) != (t["form"] <= tol)
            bad = abs(err) > 1.2 or flips
            if bad: wrong[k].append(f)
            cells.append("%6.2f %+6.2f %s" % (v, err, "FLIP" if flips else ("out " if abs(err) > 1.2 else "ok  ")))
        print("  %-7s %-12s %4.0f  %6.2f | %s | %s | %s" % (f, req[f][0], tol, t["form"], *cells))
    print("  features outside the band or with the form verdict flipped:", {k: len(v) for k, v in wrong.items()}, wrong["raw"])
# least squares against minimum zone on the true surfaces
print("\nleast-squares zone (p-v about the origin) against minimum zone, true surface, roundness features:")
for f in isim.ORDER:
    if isim.FEATURES[f]["tol"][0] != "roundness": continue
    ls = max(np.ptp(isim.assess_profile(th, isim.surface(f, j, th))) for j in range(3))
    print("  %-6s LS %.2f  MZ %.2f  difference %.2f" % (f, ls, isim.truth(f)["form"], ls - isim.truth(f)["form"]))

print("\ncertified scan against the shop record, amplitude spectra (no clamping angle needed), middle section:")
seed = json.load(open(os.path.join(T, "environment", "rig", "sealed", "seed.json")))["scan_seed"]
for f in ("RJ-44", "CB-22"):
    r = [x for x in tester if x["feature"] == f][0]
    rec = secs(os.path.join(D, "measurements", os.path.basename(r["file"])))[1]
    sc = isim.scan(f, 0, seed)[1][1]
    a = 2 * np.abs(np.fft.rfft((rec - rec.mean()) * 1000.0) / N); b = 2 * np.abs(np.fft.rfft((sc - sc.mean()) * 1000.0) / N)
    print("  %-6s orders 2-50 where record and scan differ by more than 0.5 um: %s" % (
        f, ", ".join("%d (%.2f, %.2f)" % (n, a[n], b[n]) for n in range(2, 51) if abs(a[n] - b[n]) > 0.5)))

print("\ndrawing tolerance (agent-visible) against the sealed tolerance:")
for f in isim.ORDER:
    t = isim.truth(f)
    if req[f][1] != t["tol"]:
        print("  %-6s drawing %.0f  sealed %.1f  true form %.2f" % (f, req[f][1], t["tol"], t["form"]))
