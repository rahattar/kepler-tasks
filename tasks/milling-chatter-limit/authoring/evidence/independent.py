"""A second MS-CH program, written separately from solution/chatter.py and sharing no code with it:

    python3 independent.py JOB_DIR OUT_JSON

- FRFs: each tap test (converted to receptance, sign and accelerometer mass corrected as its header says) is fitted
  with a two-mode model (scipy least squares on the complex receptance, starting from the two largest peaks), and
  the stability is computed on the fitted model on a 0.1 Hz grid, not on the measured points.
- Eigenvalues: numerically, from the 2 x 2 oriented FRF matrix at each frequency (numpy.linalg.eigvals), not by the
  quadratic formula.
- Speed: each lobe's spindle speed n(f) is formed explicitly, and the lobe's depth is interpolated where n(f)
  crosses the speed of the operation; the lowest over all lobes and branches is the limit.
- Records: the same reading of the setup sheet, the machine log and the tap test headers as MS-CH and the package
  format call for, written independently.
"""
import csv, glob, json, math, os, re, sys
import numpy as np
from scipy.optimize import least_squares
from scipy.signal import find_peaks

COEFF_FILE = "/app/data/docs/cutting_coefficients.md"


def field(text, key):
    for ln in text.splitlines():
        if ln.startswith("- %s:" % key):
            return ln.split(":", 1)[1].strip().rstrip(".")
    raise KeyError(key)


def setup(d):
    t = open(os.path.join(d, "setup_sheet.md")).read()
    tool = field(t, "Tool assembly")
    op = field(t, "Operation").lower()
    out = {"machine": field(t, "Machine"), "assembly": tool.split(":")[0].strip(), "material": field(t, "Material")}
    out["D"] = float(re.search(r"(\d+(?:\.\d+)?) mm", tool.split(":", 1)[1]).group(1)) / 1000
    fitted = re.search(r"(\d+) inserts fitted", tool)
    out["teeth"] = int(fitted.group(1)) if fitted else int(re.search(r"(\d+) flutes", tool).group(1))
    st = re.search(r"stickout (\d+) mm", tool)
    out["stickout"] = int(st.group(1)) if st else None
    out["up"] = "conventional" in op
    out["feed"] = re.search(r"machine ([xy]) axis", op).group(1).upper()
    pct = re.search(r"stepover (\d+(?:\.\d+)?) percent", op)
    out["ae"] = float(pct.group(1)) / 100 * out["D"] if pct else float(re.search(r"radial depth of cut (\d+(?:\.\d+)?) mm", op).group(1)) / 1000
    out["S"] = float(re.search(r"S(\d+)", field(t, "Programmed spindle speed")).group(1))
    return out


def speed_and_validity(d, S):
    with open(os.path.join(d, "machine_log.csv")) as fh:
        log = list(csv.DictReader(fh))
    limit, spindle_work = None, ""
    for r in sorted(log, key=lambda r: r["date"]):
        txt = r["description"].lower()
        m = re.search(r"maximum speed parameter set to (\d+) rpm", txt)
        if m:
            limit = float(m.group(1))
        if "spindle" in txt and re.search(r"cartridge|bearing|rebuil|replac", txt):
            spindle_work = max(spindle_work, r["date"])
    return (min(S, limit) if limit else S), spindle_work


def tap(p):
    with open(p) as fh:
        lines = fh.read().splitlines()
    meta = [l[1:].strip() for l in lines if l.startswith("#")]
    body = [l for l in lines if not l.startswith("#")]
    first = meta[0]
    rec = {"date": re.findall(r"\d{4}-\d{2}-\d{2}", first)[-1],
           "assembly": re.search(r"assembly ([^,\s]+)", first).group(1),
           "stickout": int(re.search(r"stickout (\d+) mm", first).group(1)) if "stickout not" not in first else None}
    for m in meta[1:]:
        if m.startswith("Axis:"):
            rec["axis"] = m.split()[1]
            rec["opposite"] = "opposite flank" in m
        elif m.startswith("Accelerometer:"):
            rec["mass"] = float(re.search(r"(\d+(?:\.\d+)?) g", m).group(1)) / 1000
            rec["uncorrected"] = "not corrected" in m
        elif m.startswith("Quantity:"):
            rec["q"] = m.split(":")[1].split(",")[0].strip()
    hdr = body[0].split(",")
    arr = np.array([[float(v) for v in l.split(",")] for l in body[1:]])
    f = arr[:, hdr.index("freq_hz")]
    H = arr[:, hdr.index("real")] + 1j * arr[:, hdr.index("imag")]
    jw = 1j * 2 * np.pi * f
    G = {"receptance": H, "mobility": H / jw, "accelerance": H / jw ** 2}[rec["q"]]
    if rec["opposite"]:
        G = -G
    if rec["uncorrected"]:
        G = G / (1 + rec["mass"] * (2 * np.pi * f) ** 2 * G)
    rec["f"], rec["G"] = f, G
    return rec


def model(p, f):
    w = 2 * np.pi * f
    G = np.zeros_like(w, dtype=complex)
    for i in range(0, len(p), 3):
        fn, z, k = p[i], p[i + 1], 10 ** p[i + 2]
        wn = 2 * np.pi * fn
        G += (wn ** 2 / k) / (wn ** 2 - w ** 2 + 2j * z * wn * w)
    return G


def fit(f, G):
    pk, _ = find_peaks(np.abs(G), distance=200)
    pk = sorted(pk, key=lambda i: -np.abs(G[i]))[:2]
    p0 = []
    for i in sorted(pk):
        k0 = 1 / (2 * 0.03 * abs(G[i]))
        p0 += [f[i], 0.03, math.log10(k0)]
    scale = np.abs(G).max()

    def res(p):
        r = (model(p, f) - G) / scale
        return np.concatenate([r.real, r.imag])
    return least_squares(res, p0, x_scale="jac").x


def coeff(material):
    for ln in open(COEFF_FILE):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] == material:
            return float(cells[1]) * 1e6, float(cells[2])
    raise KeyError(material)


def stability(n0, Gf, Gn, f, N, Kt, Kr, up, ae, D):
    if up:
        a, b = 0.0, math.acos(1 - 2 * ae / D)
    else:
        a, b = math.acos(2 * ae / D - 1), math.pi

    def prim(p):
        return np.array([[math.cos(2 * p) - 2 * Kr * p + Kr * math.sin(2 * p), -math.sin(2 * p) - 2 * p + Kr * math.cos(2 * p)],
                         [-math.sin(2 * p) + 2 * p + Kr * math.cos(2 * p), -math.cos(2 * p) - 2 * Kr * p - Kr * math.sin(2 * p)]]) / 2
    A = prim(b) - prim(a)
    Phi = np.empty((len(f), 2, 2), dtype=complex)
    Phi[:, 0, 0] = A[0, 0] * Gf; Phi[:, 0, 1] = A[0, 1] * Gn
    Phi[:, 1, 0] = A[1, 0] * Gf; Phi[:, 1, 1] = A[1, 1] * Gn
    mu = np.linalg.eigvals(Phi)
    mu = np.sort_complex(mu)          # a consistent order of the two branches along f
    best = math.inf
    w = 2 * np.pi * f
    for j in range(2):
        Lam = -1.0 / mu[:, j]
        kap = Lam.imag / Lam.real
        alim = -2 * math.pi * Lam.real * (1 + kap ** 2) / (N * Kt)
        eps = math.pi - 2 * np.arctan(kap)
        for k in range(100):
            n = 60 * w / (N * (eps + 2 * math.pi * k))
            g = n - n0
            cross = np.where((g[:-1] * g[1:] < 0) & (alim[:-1] > 0) & (alim[1:] > 0))[0]
            for i in cross:
                t = g[i] / (g[i] - g[i + 1])
                best = min(best, alim[i] + t * (alim[i + 1] - alim[i]))
    return best


def run(d, out):
    s = setup(d)
    n, after = speed_and_validity(d, s["S"])
    taps = [tap(p) for p in sorted(glob.glob(os.path.join(d, "tap_tests", "*.csv")))]
    good = [t for t in taps if t["assembly"] == s["assembly"] and t["stickout"] == s["stickout"] and t["date"] > after]
    latest = max(t["date"] for t in good)
    by_axis = {t["axis"]: t for t in good if t["date"] == latest}
    f = np.arange(50.0, 8000.0, 0.1)
    G = {ax: model(fit(t["f"], t["G"]), f) for ax, t in by_axis.items()}
    Gf, Gn = (G["X"], G["Y"]) if s["feed"] == "X" else (G["Y"], G["X"])
    Kt, Kr = coeff(s["material"])
    a = stability(n, Gf, Gn, f, s["teeth"], Kt, Kr, s["up"], s["ae"], s["D"])
    with open(out, "w") as fh:
        json.dump({"stable_depth_mm": round(a * 1000, 4)}, fh)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
