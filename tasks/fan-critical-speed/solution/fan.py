"""Reference program: python3 fan.py FAN_DIR OUT_JSON

Assesses an overhung fan with its new impeller to MS-RD and writes its two lowest critical speeds (rpm):
- reads the OEM datasheet (shaft sections, bearings, pedestals, coupling hub, impeller as built), the asset register's
  rotor changes, the maintenance log, the impact test reports and the new impeller;
- dates each rotor change by its work order's date in the maintenance log (the register's `entered` date is when the
  entry was made, which can be after the work);
- picks the latest impact test of the fan as installed (condition "as installed") made after the last work on the
  pedestals (regrouting, anchor bolts); a test with a support temporarily changed (a stay removed) does not
  represent the fan as it runs;
- identifies the pedestal springs (horizontal and vertical, the same for both pedestals) so that the model of the
  rotor as it stood on the test date has the test's lowest standstill frequencies (Brent root in log stiffness);
- fits the new impeller to the rotor as it is now and finds the critical speeds: the running speeds W at which
  K - W^2 (M - iG) is singular (gyroscopic coupling included), the two lowest.
The model is the one MS-RD clause 2 sets out: Euler-Bernoulli shaft elements of at most 20 mm, rigid impeller and hub,
bearing springs in series with pedestal masses on horizontal and vertical springs.
"""
import csv, glob, json, os, re, sys
import numpy as np
from scipy.linalg import eigh
from scipy.optimize import brentq

E, RHO = 207e9, 7850.0


def parse(d):
    t = open(os.path.join(d, "fan_datasheet.md")).read()
    S = {}
    S["shaft"] = [[float(a) / 1000, float(b) / 1000, float(c) / 1000] for a, b, c in re.findall(r"^\| (\d+) \| (\d+) \| (\d+) \|$", t, re.M)]
    b = re.search(r"drive end at (\d+) mm and fan end at (\d+) mm", t)
    S["bearings"] = [float(b.group(1)) / 1000, float(b.group(2)) / 1000]
    S["kb"] = float(re.search(r"radial stiffness ([\d.]+) GN/m", t).group(1)) * 1e9
    S["mp"] = float(re.search(r"effective mass (\d+) kg", t).group(1))
    h = re.search(r"Coupling hub.*?center of gravity at (\d+) mm; mass ([\d.]+) kg; transverse moment of inertia ([\d.]+) kg m2; polar moment of inertia ([\d.]+)", t)
    S["hub"] = (float(h.group(1)) / 1000, float(h.group(2)), float(h.group(3)), float(h.group(4)))
    i = re.search(r"Impeller: center of gravity at the shaft end, (\d+) mm; mass ([\d.]+) kg; transverse moment of inertia about the center of gravity ([\d.]+) kg m2; polar moment of inertia \(WR2\) ([\d.]+)", t)
    S["zimp"] = float(i.group(1)) / 1000
    S["imp"] = [float(i.group(2)), float(i.group(3)), float(i.group(4))]
    S["changes"] = list(csv.DictReader(open(os.path.join(d, "rotor_changes.csv"))))
    n = open(os.path.join(d, "new_impeller.md")).read()
    m = re.search(r"Mass ([\d.]+) kg; transverse moment of inertia about the center of gravity ([\d.]+) kg m2; polar moment of inertia \(WR2\) ([\d.]+)", n)
    S["new"] = [float(x) for x in m.groups()]
    S["tests"] = []
    for p in sorted(glob.glob(os.path.join(d, "impact_tests", "*.md"))):
        r = open(p).read()
        S["tests"].append(dict(date=re.search(r", (\d{4}-\d\d-\d\d)", r).group(1), cond=re.search(r"Condition: ([^\n]*)", r).group(1),
                               fH=float(re.search(r"\| horizontal \| ([\d.]+) \|", r).group(1)), fV=float(re.search(r"\| vertical \| ([\d.]+) \|", r).group(1))))
    S["log"] = list(csv.DictReader(open(os.path.join(d, "maintenance_log.csv"))))
    return S


def rotor_at(S, date, use_entered=False):
    sh = [list(s) for s in S["shaft"]]; imp = list(S["imp"]); hub = list(S["hub"])
    work = {r["work_order"]: r["date"] for r in S["log"]}
    for c in S["changes"]:
        c["date"] = c["entered"] if use_entered else work.get(c["work_order"], c["entered"])
    for c in sorted(S["changes"], key=lambda c: c["date"]):
        if date is not None and c["date"] > date: continue
        if c["part"] == "coupling hub":
            hub[1 + {"mass_kg": 0, "transverse_inertia_kg_m2": 1, "polar_inertia_kg_m2": 2}[c["property"]]] = float(c["value"])
        if c["part"] == "impeller":
            k = {"mass_kg": 0, "transverse_inertia_kg_m2": 1, "polar_inertia_kg_m2": 2}[c["property"]]
            imp[k] = float(c["value"])
        m = re.match(r"shaft section (\d+)-(\d+) mm", c["part"])
        if m:
            for s in sh:
                if abs(s[0] * 1000 - float(m.group(1))) < 0.5 and abs(s[1] * 1000 - float(m.group(2))) < 0.5:
                    s[2] = float(c["value"]) / 1000
    S["hub_now"] = tuple(hub)
    return sh, imp


def assemble(S, sh, imp, kH, kV, mesh=0.02):
    pts = {0.0}
    for z0, z1, d in sh:
        n = max(1, int(np.ceil((z1 - z0) / mesh))); pts.update(np.round(np.linspace(z0, z1, n + 1), 6))
    pts.update([round(S["hub"][0], 6), round(S["zimp"], 6)] + [round(b, 6) for b in S["bearings"]])
    z = np.array(sorted(pts)); N = len(z); nd = 4 * N + 4; S["_z"] = z
    K = np.zeros((nd, nd)); M = np.zeros((nd, nd)); G = np.zeros((nd, nd))
    for e in range(N - 1):
        L = z[e + 1] - z[e]; zm = 0.5 * (z[e] + z[e + 1])
        d = next(s[2] for s in sh if s[0] - 1e-9 <= zm <= s[1] + 1e-9)
        A = np.pi * d * d / 4; I = np.pi * d ** 4 / 64
        k = E * I / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L], [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
        m = RHO * A * L / 420 * np.array([[156, 22 * L, 54, -13 * L], [22 * L, 4 * L * L, 13 * L, -3 * L * L], [54, 13 * L, 156, -22 * L], [-13 * L, -3 * L * L, -22 * L, 4 * L * L]])
        for iu, ia in ((0, 2), (1, 3)):
            idx = [4 * e + iu, 4 * e + ia, 4 * e + 4 + iu, 4 * e + 4 + ia]
            K[np.ix_(idx, idx)] += k; M[np.ix_(idx, idx)] += m
        for nn in (e, e + 1):
            G[4 * nn + 2, 4 * nn + 3] += RHO * 2 * I * L / 2; G[4 * nn + 3, 4 * nn + 2] -= RHO * 2 * I * L / 2
    node = lambda zz: int(np.argmin(abs(z - zz)))
    hub = S.get("hub_now", S["hub"])
    for zz, (m, Id, Ip) in ((hub[0], hub[1:]), (S["zimp"], imp)):
        n = node(zz)
        M[4 * n, 4 * n] += m; M[4 * n + 1, 4 * n + 1] += m; M[4 * n + 2, 4 * n + 2] += Id; M[4 * n + 3, 4 * n + 3] += Id
        G[4 * n + 2, 4 * n + 3] += Ip; G[4 * n + 3, 4 * n + 2] -= Ip
    for j, zb in enumerate(S["bearings"]):
        n = node(zb); p = 4 * N + 2 * j
        for s, k in ((0, kH), (1, kV)):
            i = 4 * n + s; q = p + s
            K[i, i] += S["kb"]; K[q, q] += S["kb"] + k; K[i, q] -= S["kb"]; K[q, i] -= S["kb"]; M[q, q] += S["mp"]
    return K, M, G, N


def standstill(S, sh, imp, kH, kV):
    K, M, G, N = assemble(S, sh, imp, kH, kV)
    lam, V = eigh(K, M)
    hor = np.zeros(K.shape[0], bool); hor[0::4][:N] = True; hor[2:4 * N:4] = True; hor[4 * N] = hor[4 * N + 2] = True
    out = {}
    for i in range(len(lam)):
        dd = "H" if np.sum(V[hor, i] ** 2) > 0.5 * np.sum(V[:, i] ** 2) else "V"
        out.setdefault(dd, np.sqrt(lam[i]) / (2 * np.pi))
    return out


def identify(S, sh, imp, fH, fV):
    gH = lambda lk: standstill(S, sh, imp, np.exp(lk), 1e9)["H"] - fH
    gV = lambda lk: standstill(S, sh, imp, 1e9, np.exp(lk))["V"] - fV
    return np.exp(brentq(gH, np.log(1e6), np.log(1e11), xtol=1e-7)), np.exp(brentq(gV, np.log(1e6), np.log(1e11), xtol=1e-7))


def criticals(S, sh, imp, kH, kV, skip=()):
    K, M, G, N = assemble(S, sh, imp, kH, kV)
    if "gyro" in skip:
        G = 0 * G
    mu, V = eigh(M - 1j * G, K.astype(complex))
    order = [i for i in np.argsort(-mu) if mu[i] > 0]
    if "backward" in skip:                   # forward whirl only, judged at the impeller
        z = S["zimp"]; n = int(np.argmin(abs(S["_z"] - z)))
        order = [i for i in order if abs(V[4 * n + 1, i] + 1j * V[4 * n, i]) < abs(V[4 * n + 1, i] - 1j * V[4 * n, i])]
    return [float(60 / (2 * np.pi) / np.sqrt(mu[i])) for i in order[:2]]


def assess(d, skip=()):
    S = parse(d)
    support_work = [r["date"] for r in S["log"] if re.search(r"regrout|soleplate|anchor bolt|pedestal.*(replac|modif|stiffen)",
                    r["description"], re.I) and not re.search(r"refitted", r["description"])]
    last = max(support_work) if support_work else "0"
    tests = S["tests"]
    if "first" in skip:
        t = min(tests, key=lambda t: t["date"])
    elif "condition" in skip:
        t = max([t for t in tests if t["date"] > last] or tests, key=lambda t: t["date"])
    else:
        ok = [t for t in tests if t["cond"].strip().lower().startswith("as installed") and t["date"] > last]
        t = max(ok, key=lambda t: t["date"])
    if "shaft" in skip:
        S["changes"] = [c for c in S["changes"] if not c["part"].startswith("shaft")]
    at = None if "test_rotor" in skip else ("0000" if "datasheet_rotor" in skip else t["date"])
    sh, imp = rotor_at(S, at, "entered" in skip)
    kH, kV = identify(S, sh, imp, t["fH"], t["fV"])
    sh, _ = rotor_at(S, None, "entered" in skip)
    c = criticals(S, sh, S["new"], kH, kV, skip)
    return {"first_critical_rpm": round(c[0], 1), "second_critical_rpm": round(c[1], 1)}


def main(pkg, out):
    with open(out, "w") as f:
        json.dump(assess(pkg), f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
