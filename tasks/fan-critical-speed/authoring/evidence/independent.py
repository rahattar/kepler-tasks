"""A second MS-RD program, written separately from solution/fan.py and sharing no code with it:

    python3 independent.py FAN_DIR OUT_JSON

- Model: Euler-Bernoulli shaft elements of at most 30 mm with LUMPED mass (half of each element's mass and of its
  rotary and polar inertia at each node), not the reference's consistent mass at 20 mm; the planes assembled
  separately for the standstill identification.
- Identification: bisection on the logarithm of each pedestal stiffness, horizontal and vertical plane each on its own.
- Critical speeds: a Campbell sweep. At each running speed W the state-space eigenvalues of the gyroscopic system give
  the natural frequencies; the count of natural frequencies below W rises by one at each critical speed. The sweep
  finds the speeds where the count changes and bisects each to 1e-6 of the speed. The reference instead solves the
  synchronous problem K - W^2 (M - iG) directly.
- Records: rotor changes dated by their work order in the maintenance log; the latest impact test of the fan as
  installed after the last pedestal work.
"""
import csv, glob, json, math, os, re, sys
import numpy as np
from scipy.linalg import eig, eigh

E_STEEL, RHO_STEEL = 207e9, 7850.0
DZ = 0.03


def numbers(s):
    """The numbers in a line, leaving out digits that are part of a unit or a name (kg m2, WR2)."""
    return [float(x) for x in re.findall(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?", s)]


def read_fan(d):
    lines = open(os.path.join(d, "fan_datasheet.md")).read().splitlines()
    fan = {"sections": [], "hub": None, "imp": None}
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")] if ln.startswith("|") else []
        if len(cells) == 3 and all(re.fullmatch(r"\d+", c) for c in cells):
            a, b, dia = (float(c) / 1000 for c in cells)
            fan["sections"].append([a, b, dia])
        low = ln.lower()
        if low.startswith("- bearings"):
            nums = numbers(ln.split(";")[0])
            fan["bearings"] = nums[:2] and [nums[0] / 1000, nums[1] / 1000]
            fan["kb"] = numbers(ln.split("radial stiffness")[1])[0] * 1e9
        if low.startswith("- pedestals"):
            fan["mp"] = numbers(ln.split("effective mass")[1])[0]
        if low.startswith("- coupling hub"):
            n = numbers(ln.split(":", 1)[1])
            fan["hub"] = {"z": n[0] / 1000, "m": n[1], "Id": n[2], "Ip": n[3]}
        if low.startswith("- impeller"):
            n = numbers(ln.split(":", 1)[1])
            fan["imp"] = {"z": n[0] / 1000, "m": n[1], "Id": n[2], "Ip": n[3]}
    n = numbers(open(os.path.join(d, "new_impeller.md")).read().split("- Mass", 1)[1])
    fan["new"] = {"m": n[0], "Id": n[1], "Ip": n[2]}
    with open(os.path.join(d, "maintenance_log.csv")) as f:
        fan["log"] = list(csv.DictReader(f))
    with open(os.path.join(d, "rotor_changes.csv")) as f:
        fan["register"] = list(csv.DictReader(f))
    fan["tests"] = []
    for p in glob.glob(os.path.join(d, "impact_tests", "*.md")):
        txt = open(p).read()
        rec = {"date": re.findall(r"\d{4}-\d{2}-\d{2}", txt.splitlines()[0])[-1]}
        for ln in txt.splitlines():
            if ln.lower().startswith("- condition:"):
                rec["condition"] = ln.split(":", 1)[1].strip().rstrip(".").lower()
            cells = [c.strip().lower() for c in ln.strip().strip("|").split("|")] if ln.startswith("|") else []
            if len(cells) == 2 and cells[0] in ("horizontal", "vertical"):
                rec[cells[0][0]] = float(cells[1])
        fan["tests"].append(rec)
    return fan


def state_on(fan, date):
    """Sections, hub and impeller after every change whose work was done on or before `date` (None: all)."""
    work_date = {r["work_order"]: r["date"] for r in fan["log"]}
    secs = [list(s) for s in fan["sections"]]
    hub, imp = dict(fan["hub"]), dict(fan["imp"])
    key = {"mass_kg": "m", "transverse_inertia_kg_m2": "Id", "polar_inertia_kg_m2": "Ip"}
    rows = sorted(fan["register"], key=lambda r: work_date.get(r["work_order"], r["entered"]))
    for r in rows:
        when = work_date.get(r["work_order"], r["entered"])
        if date is not None and when > date:
            continue
        part, val = r["part"].strip().lower(), float(r["value"])
        if part == "impeller":
            imp[key[r["property"]]] = val
        elif part == "coupling hub":
            hub[key[r["property"]]] = val
        elif part.startswith("shaft section"):
            a, b = (x / 1000 for x in numbers(part)[:2])
            for s in secs:
                if abs(s[0] - a) < 1e-4 and abs(s[1] - b) < 1e-4:
                    s[2] = val / 1000
    return secs, hub, imp


def mesh(fan, secs, zimp):
    marks = {round(x, 6) for s in secs for x in s[:2]} | {round(fan["hub"]["z"], 6), round(zimp, 6)}
    marks |= {round(b, 6) for b in fan["bearings"]}
    marks = sorted(marks)
    z = [marks[0]]
    for a, b in zip(marks[:-1], marks[1:]):
        n = max(1, math.ceil((b - a) / DZ - 1e-9))
        z += list(np.linspace(a, b, n + 1)[1:])
    return np.array(z)


def matrices(fan, secs, hub, imp, kH, kV):
    """Lumped-mass matrices in the global order [u0, v0, au0, av0, u1, ...] plus 2 DOFs per pedestal."""
    z = mesh(fan, secs, fan["imp"]["z"]); n = len(z); nd = 4 * n + 4
    K = np.zeros((nd, nd)); M = np.zeros(nd); G = np.zeros((nd, nd))

    def dia(zz):
        for a, b, d in secs:
            if a - 1e-9 <= zz <= b + 1e-9:
                return d
        raise ValueError("no section at %g" % zz)

    for e in range(n - 1):
        L = z[e + 1] - z[e]; d = dia(0.5 * (z[e] + z[e + 1]))
        I = math.pi * d ** 4 / 64; A = math.pi * d ** 2 / 4; EI = E_STEEL * I
        ke = EI / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                                     [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
        for t, r in ((0, 2), (1, 3)):
            dofs = [4 * e + t, 4 * e + r, 4 * (e + 1) + t, 4 * (e + 1) + r]
            K[np.ix_(dofs, dofs)] += ke
        for node in (e, e + 1):
            M[4 * node] += RHO_STEEL * A * L / 2; M[4 * node + 1] += RHO_STEEL * A * L / 2
            M[4 * node + 2] += RHO_STEEL * I * L / 2; M[4 * node + 3] += RHO_STEEL * I * L / 2
            G[4 * node + 2, 4 * node + 3] += RHO_STEEL * I * L; G[4 * node + 3, 4 * node + 2] -= RHO_STEEL * I * L
    at = lambda zz: int(np.argmin(np.abs(z - zz)))
    for body, zz in ((hub, hub["z"]), (imp, fan["imp"]["z"])):
        i = at(zz)
        M[4 * i] += body["m"]; M[4 * i + 1] += body["m"]; M[4 * i + 2] += body["Id"]; M[4 * i + 3] += body["Id"]
        G[4 * i + 2, 4 * i + 3] += body["Ip"]; G[4 * i + 3, 4 * i + 2] -= body["Ip"]
    for j, zb in enumerate(fan["bearings"]):
        i = at(zb)
        for t, k in ((0, kH), (1, kV)):
            s, p = 4 * i + t, 4 * n + 2 * j + t
            K[s, s] += fan["kb"]; K[p, p] += fan["kb"] + k; K[s, p] -= fan["kb"]; K[p, s] -= fan["kb"]
            M[p] += fan["mp"]
    return K, M, G, n


def lowest_in_plane(fan, secs, hub, imp, k, plane):
    K, M, G, n = matrices(fan, secs, hub, imp, k, k)
    dofs = [4 * i + plane for i in range(n)] + [4 * i + 2 + plane for i in range(n)] + [4 * n + plane, 4 * n + 2 + plane]
    w2 = eigh(K[np.ix_(dofs, dofs)], np.diag(M[dofs]), eigvals_only=True, subset_by_index=[0, 0])[0]
    return math.sqrt(w2) / (2 * math.pi)


def identify(fan, secs, hub, imp, f_meas, plane):
    lo, hi = math.log(1e6), math.log(1e11)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if lowest_in_plane(fan, secs, hub, imp, math.exp(mid), plane) < f_meas:
            lo = mid
        else:
            hi = mid
    return math.exp(0.5 * (lo + hi))


def count_below(K, M, G, W):
    nd = K.shape[0]; Mi = 1.0 / M
    A = np.zeros((2 * nd, 2 * nd))
    A[:nd, nd:] = np.eye(nd)
    A[nd:, :nd] = -Mi[:, None] * K
    A[nd:, nd:] = -Mi[:, None] * (W * G)
    lam = eig(A, right=False)
    w = np.abs(lam.imag[lam.imag > 1e-9])
    return int(np.sum(w < W))


def critical_speeds(K, M, G, how_many=2):
    found, W0 = [], 2 * math.pi * 50 / 60
    c0 = count_below(K, M, G, W0)
    W = W0
    while len(found) < how_many and W < 2 * math.pi * 20000 / 60:
        W1 = W * 1.02
        c1 = count_below(K, M, G, W1)
        if c1 != c0:
            a, b = W, W1
            while (b - a) / b > 1e-6:
                m = 0.5 * (a + b)
                if count_below(K, M, G, m) == c0:
                    a = m
                else:
                    b = m
            found += [0.5 * (a + b)] * (c1 - c0)
            c0 = c1
        W = W1
    return [w * 60 / (2 * math.pi) for w in found[:how_many]]


def run(d, out):
    fan = read_fan(d)
    pedestal_work = [r["date"] for r in fan["log"]
                     if re.search(r"grout|soleplate|anchor bolt", r["description"], re.I)]
    after = max(pedestal_work) if pedestal_work else ""
    usable = [t for t in fan["tests"] if t.get("condition", "").startswith("as installed") and t["date"] > after]
    test = sorted(usable, key=lambda t: t["date"])[-1]
    secs, hub, imp = state_on(fan, test["date"])
    kH = identify(fan, secs, hub, imp, test["h"], 0)
    kV = identify(fan, secs, hub, imp, test["v"], 1)
    secs, hub, _ = state_on(fan, None)
    K, M, G, n = matrices(fan, secs, hub, dict(fan["new"]), kH, kV)
    c = critical_speeds(K, M, G)
    with open(out, "w") as f:
        json.dump({"first_critical_rpm": round(c[0], 1), "second_critical_rpm": round(c[1], 1)}, f)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
