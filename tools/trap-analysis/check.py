"""Independent check of bore-form-acceptance's instrument layer on the shipped records.

    python3 tools/trap-analysis/check.py tasks/bore-form-acceptance/environment/data

Reads only the agent-visible data. Prints: (1) the FM-7 filter and a least-squares zone on each RT-1 record against
the inspection report; (2) spindle-frame averages of the filtered Fourier coefficients, pooled and split at the
2026-09-30 service, with a z score on the modulus of the mean, the phase lock (mean resultant length) and the
amplitude ratio across records; (3) the other orders' largest phase lock. Used for docs/trap-analysis-2026-11-11.md.
"""
import csv, sys, os
import numpy as np
np.seterr(all="ignore")
D = sys.argv[1]
idx = list(csv.DictReader(open(os.path.join(D, "measurement_index.csv"))))
tol = {r["feature"]: (r["form_characteristic"], float(r["form_tolerance_um"])) for r in csv.DictReader(open(os.path.join(D, "drawing_requirements.csv")))}
W = lambda n: np.exp(-np.pi * (0.4697 * n / 50.0) ** 2)

def sections(path):
    rows = list(csv.DictReader(open(path)))
    out = {}
    for r in rows:
        out.setdefault(float(r["section_mm"]), []).append(float(r["radius_mm"]))
    return [np.array(v) for k, v in sorted(out.items())]

def coeffs(r):
    """complex Fourier coefficients c_n (um) of the deviation, so that dev = sum 2 Re(c_n e^{i n th})"""
    dev = (r - r.mean()) * 1000.0
    return np.fft.rfft(dev) / len(dev)

def profile(c, N, drop=()):
    c = c.copy(); n = np.arange(len(c))
    c[:2] = 0
    c = c * W(n)
    for k in drop: c[k] = 0
    return np.fft.irfft(c * N, N), c

tester = [r for r in idx if "RT-1" in r["instrument"]]
rep = {}
for line in open(os.path.join(D, "docs", "inspection_report.md")):
    p = [x.strip() for x in line.split("|")]
    if len(p) > 4 and p[1][:2] in ("CB", "GB", "RJ"):
        rep[p[1]] = float(p[3])
C = {}   # feature -> array [section, order] of filtered complex coefficients
print("1. FM-7 filter on each RT-1 record as it stands, peak-to-valley about the origin (= least-squares zone)")
print("   feature  date        mine(max section)  report  tol   char")
for r in tester:
    f = r["feature"]; secs = sections(os.path.join(D, "measurements", os.path.basename(r["file"])))
    pv = []; cs = []
    for s in secs:
        prof, c = profile(coeffs(s), len(s)); pv.append(prof.max() - prof.min()); cs.append(c)
    C[f] = np.array(cs)
    print("   %-7s  %s  %6.1f             %5.1f   %4.0f  %s" % (f, r["measured_on"], max(pv), rep[f], tol[f][1], tol[f][0]))

orders = np.arange(2, 51)
def stats(feats, label):
    # one vector per record: the mean over its three sections
    V = np.array([C[f].mean(axis=0) for f in feats])          # [record, order]
    m = V.mean(axis=0); 
    sd = np.sqrt((np.abs(V - m) ** 2).sum(axis=0) / max(len(feats) - 1, 1))
    se = sd / np.sqrt(len(feats))
    z = np.abs(m) / np.where(se > 0, se, np.nan)
    R = np.abs((V / np.abs(V)).mean(axis=0))                  # mean resultant length of the phases
    amp = 2 * np.abs(V)                                       # single-sided amplitude per record
    ratio = amp.max(axis=0) / amp.min(axis=0)
    top = sorted(orders, key=lambda n: -z[n])[:6]
    print("\n%s (%d records)" % (label, len(feats)))
    print("   order  |mean| amp um   z=|mean|/se   phase-lock R   amp max/min   mean phase rad")
    for n in top:
        print("   %3d    %6.2f         %7.1f       %5.2f          %6.2f        %+5.2f" % (n, 2 * abs(m[n]), z[n], R[n], ratio[n], np.angle(m[n])))
    return m, z, R

feats = [r["feature"] for r in tester]
before = [r["feature"] for r in tester if r["measured_on"] <= "2026-09-30"]
after = [r["feature"] for r in tester if r["measured_on"] > "2026-09-30"]
print("\n2. Spindle-frame averages of the filtered coefficients, orders 2-50; top six by z")
mp, zp, Rp = stats(feats, "pooled over the whole campaign")
mb, zb, Rb = stats(before, "before the 2026-09-30 service: " + " ".join(before))
ma, za, Ra = stats(after, "after it: " + " ".join(after))
for n in (23, 29):
    print("   order %d pooled: z %.1f, R %.2f; before amp %.2f phase %+.2f; after amp %.2f phase %+.2f; phase moved %.2f rad" % (
        n, zp[n], Rp[n], 2 * abs(mb[n]), np.angle(mb[n]), 2 * abs(ma[n]), np.angle(ma[n]), abs(np.angle(ma[n] / mb[n]))))
print("   orders with pooled z > 3:", [int(n) for n in orders if zp[n] > 3], "| before:", [int(n) for n in orders if zb[n] > 3], "| after:", [int(n) for n in orders if za[n] > 3])
print("   orders with R > 0.9 pooled:", [int(n) for n in orders if Rp[n] > 0.9], "| before:", [int(n) for n in orders if Rb[n] > 0.9], "| after:", [int(n) for n in orders if Ra[n] > 0.9])

# machine motion peak to valley per state, from orders 23 and 29 only
th = np.arange(1800) / 1800 * 2 * np.pi
for lab, m in (("before", mb), ("after", ma)):
    e = sum(2 * np.real(m[n] * np.exp(1j * n * th)) for n in (23, 29))
    print("   %s: error motion from orders 23+29, peak to valley %.1f um" % (lab, e.max() - e.min()))

print("\n3. Largest phase lock at any order other than 23 and 29")
for lab, R in (("pooled", Rp), ("before", Rb), ("after", Ra)):
    others = [(float(R[n]), int(n)) for n in orders if n not in (23, 29) and R[n] == R[n]]
    print("   %-7s %.2f at order %d" % (lab, *max(others)))
