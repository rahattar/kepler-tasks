"""Reference program: python3 chatter.py JOB_DIR OUT_JSON

Writes the MS-CH stability limit of a milling job's operation (stable_depth_mm):
- reads the setup sheet (machine, tool assembly, diameter, the teeth that cut: the inserts fitted in a face mill
  body, or the flutes of an end mill; stickout; material; up or down milling; the feed axis; the radial depth in mm
  or as a stepover percentage; the programmed spindle speed) and the machine log;
- the speed of the operation is the programmed speed, or the machine's spindle speed limit when the log sets a lower
  one (the control clamps the programmed speed to it);
- the tap tests used are those of the job's assembly at the job's stickout, made after the last work on the spindle
  (a rebuilt or replaced spindle changes the tool-tip dynamics); of those, the latest pair (X and Y);
- each tap test is turned into the tool-tip receptance: the quantity measured (receptance, mobility or accelerance)
  converted, the sign reversed when the accelerometer was on the opposite flank, and the accelerometer's mass
  removed when the data are not corrected for it (G = Gm / (1 + m w^2 Gm));
- the receptances along the feed and normal to it are the tests along the machine axes the setup sheet names;
- the limit is the zero-order solution of MS-CH clause 2 at the speed of the operation, computed on the measured
  frequency points: for both eigenvalue branches and each lobe, the chatter frequencies at which the lobe passes
  through the speed, and the lowest positive limiting depth among them.
"""
import csv, glob, json, os, re, sys
import numpy as np

COEFFS = "/app/data/docs/cutting_coefficients.md"


def alphas(phst, phex, Kr):
    def F(p):
        return np.array([0.5 * (np.cos(2 * p) - 2 * Kr * p + Kr * np.sin(2 * p)),
                         0.5 * (-np.sin(2 * p) - 2 * p + Kr * np.cos(2 * p)),
                         0.5 * (-np.sin(2 * p) + 2 * p + Kr * np.cos(2 * p)),
                         0.5 * (-np.cos(2 * p) - 2 * Kr * p - Kr * np.sin(2 * p))])
    return F(phex) - F(phst)


def eigen_branches(f, Gx, Gy, N, Kt, Kr, phst, phex):
    axx, axy, ayx, ayy = alphas(phst, phex, Kr)
    a0 = Gx * Gy * (axx * ayy - axy * ayx); a1 = axx * Gx + ayy * Gy
    for sgn in (1, -1):
        L = -(a1 + sgn * np.sqrt(a1 ** 2 - 4 * a0 + 0j)) / (2 * a0)
        alim = -2 * np.pi * L.real / (N * Kt) * (1 + (L.imag / L.real) ** 2)
        eps = np.pi - 2 * np.arctan(L.imag / L.real)
        yield alim, eps


def limit(n0, f, Gx, Gy, N, Kt, Kr, phst, phex, skip=(), kmax=80):
    wc = 2 * np.pi * f; best = np.inf
    for alim, eps in eigen_branches(f, Gx, Gy, N, Kt, Kr, phst, phex):
        if "lobes" in skip:                      # the speed-independent lowest limit
            best = min(best, alim[alim > 0].min())
            continue
        x = wc * 60 / (N * n0) - eps
        for k in range(kmax):
            h = x - 2 * np.pi * k
            idx = np.where((np.sign(h[:-1]) != np.sign(h[1:])) & (alim[:-1] > 0) & (alim[1:] > 0))[0]
            for i in idx:
                t = h[i] / (h[i] - h[i + 1]); best = min(best, alim[i] + t * (alim[i + 1] - alim[i]))
    return best


def read_tap(p, skip=()):
    head = [l for l in open(p) if l.startswith("#")]
    h = " ".join(head)
    m = re.search(r"assembly ([^,\s]+), stickout (?:(\d+) mm|not applicable)", h)
    t = dict(path=p, assembly=m.group(1), stickout=int(m.group(2)) if m.group(2) else None,
             date=re.search(r"(\d{4}-\d\d-\d\d)", head[0]).group(1), axis=re.search(r"# Axis: (\w)", h).group(1),
             units=re.search(r"# Quantity: (\w+)", h).group(1))
    rows = [l for l in open(p) if not l.startswith("#")]
    cols = rows[0].strip().split(",")
    d = np.array([[float(x) for x in l.split(",")] for l in rows[1:]])
    f = d[:, cols.index("freq_hz")]; H = d[:, cols.index("real")] + 1j * d[:, cols.index("imag")]; w = 2 * np.pi * f
    G = H if "units" in skip else {"receptance": H, "mobility": H / (1j * w), "accelerance": -H / w ** 2}[t["units"]]
    if "sign" not in skip and re.search(r"opposite flank.*measuring along -", h):
        G = -G
    m = re.search(r"Accelerometer: ([\d.]+) g at the tool tip; data not corrected", h)
    if m and "mass" not in skip:
        G = G / (1 + float(m.group(1)) / 1000 * w ** 2 * G)
    t["f"], t["G"] = f, G
    return t


def coefficients(material, path=COEFFS):
    for row in open(path):
        c = [x.strip() for x in row.strip().strip("|").split("|")]
        if len(c) == 3 and c[0] == material:
            return float(c[1]) * 1e6, float(c[2])
    raise KeyError("no cutting coefficients for %r" % material)


def assess(d, skip=()):
    s = open(os.path.join(d, "setup_sheet.md")).read()
    asm = re.search(r"Tool assembly: ([^:\s]+):", s).group(1)
    D = float(re.search(r": (\d+) mm (?:solid carbide end mill|face mill body)", s).group(1)) / 1000
    m = re.search(r"(\d+) inserts fitted", s)
    if m and "inserts" not in skip:
        N = int(m.group(1))
    else:
        N = int(re.search(r"(\d+) (?:flutes|insert pockets)", s).group(1))
    m = re.search(r"stickout (\d+) mm", s); stick = int(m.group(1)) if m else None
    material = re.search(r"Material: (.+?)\.\n", s).group(1)
    milling = "down" if ("climb milling" in s or "milling" in skip) else "up"
    feed = "X" if "feed" in skip else re.search(r"feed along the machine (\w) axis", s).group(1)
    m = re.search(r"radial depth of cut ([\d.]+) mm", s)
    ae = float(m.group(1)) / 1000 if m else float(re.search(r"stepover (\d+) percent", s).group(1)) / 100 * D
    S = float(re.search(r"S(\d+) rpm", s).group(1))
    log = list(csv.DictReader(open(os.path.join(d, "machine_log.csv"))))
    spindle = [r["date"] for r in log if re.search(r"spindle (cartridge|bearing|rebuil|replac)", r["description"], re.I)]
    last = "0" if (not spindle or "first" in skip) else max(spindle)
    caps = sorted((r["date"], float(x)) for r in log for x in re.findall(r"maximum speed parameter set to (\d+) rpm",
                                                                      r["description"]))
    n = min(S, caps[-1][1]) if caps and "speed" not in skip else S
    taps = [read_tap(p, skip) for p in glob.glob(os.path.join(d, "tap_tests", "*.csv"))]
    ok = [t for t in taps if t["assembly"] == asm and ("stickout" in skip or t["stickout"] == stick) and t["date"] > last]
    date = (min if "first" in skip else max)(t["date"] for t in ok)
    G = {t["axis"]: t for t in ok if t["date"] == date}
    Kt, Kr = coefficients(material)
    gx, gy = G["X"], G["Y"]
    Gf, Gn = (gx["G"], gy["G"]) if feed == "X" else (gy["G"], gx["G"])
    c = np.arccos(1 - 2 * ae / D)
    phst, phex = (0.0, c) if milling == "up" else (np.arccos(2 * ae / D - 1), np.pi)
    a = limit(n, gx["f"], Gf, Gn, N, Kt, Kr, phst, phex, skip)
    return {"stable_depth_mm": round(float(a) * 1000, 4)}


def main(pkg, out):
    with open(out, "w") as f:
        json.dump(assess(pkg), f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
