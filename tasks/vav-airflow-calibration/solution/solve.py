"""Reference calibration of the AHU-3 floor: K and offset for all 40 VAV boxes from the records and five
capture-hood visits.

    python3 solve.py DATA_DIR HOOD_URL VISITS_DIR OUT_CSV

Uses only the shipped records (/app/data), the hood service and the visit reports it writes. Never reads the
service's code, the sealed definition or the verifier.

1. Zero offsets. Office boxes close outside occupied hours, so the median VP with the damper shut is the
   transducer's zero error. Firmware 2.4 has no auto-zero and takes it as the offset; a firmware 3.x box should
   read about zero, and one that does not has a failed auto-zero valve and takes it too. Lab boxes never close.
2. Visits. Every box whose calibration the records cannot settle is grouped into a class, and one box per class
   is visited: each lab box on firmware 2.4 (no auto-zero and never shut, so its zero can only be measured, and
   the zero error is per transducer), one vertical-drop elbow (the 2024 report predates the renovation and the
   west wing has only horizontal turns), and one flex connector longer than the 5 ft limit (sagging into the
   inlet). The kinked connectors on the punch list are covered by the lab box VAV-3-38, which is one of them.
3. Each visit gives K and offset from a weighted least-squares fit of flow^2 = K^2 (VP - offset) through the hood
   totals at design minimum, the midpoint and design maximum.
4. Inlet multipliers m = K / K_factory. West-wing boxes measured in 2024 take their own value (the inlets are
   unchanged; a 2.4 box's 2024 zero is unknown and taken as half of today's). Other boxes take their class:
   straight inlets (at least three diameters) 1; west horizontal elbows the fit m = 1 - a exp(-L/D / lam) to the
   five 2024 elbows; flex connectors within the specification and vertical drops m = 1 + a exp(-L/D / lam) with
   the elbows' decay length and the amplitude fitted to their own measured members (the 2024 flex box and the
   visited lab boxes with sound connectors; the visited drop); kinked and sagging connectors the visited member
   of their class.
5. Offsets: visited boxes their fitted offset; closing boxes step 1; lab boxes on firmware 3.x 0 (auto-zero).
"""
import csv, glob, json, math, os, re, sys, urllib.request
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

DATA, URL, VISITS, OUT = sys.argv[1:5]
HEALTHY_ZERO = 0.005        # in. w.c.; a working auto-zero leaves a residual far below this


def factory_k():
    note = open(os.path.join(DATA, "docs", "vav_application_note.md")).read()
    return {int(a): float(b) for a, b in re.findall(r"^\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|", note, re.M)}


KF_SIZE = factory_k()
S = pd.read_csv(os.path.join(DATA, "box_schedule.csv")).set_index("tag")
V = pd.read_csv(os.path.join(DATA, "inlet_survey.csv")).set_index("tag")
R = pd.read_csv(os.path.join(DATA, "tab_report_2024.csv")).set_index("tag")
TAGS = list(S.index)
KF = {t: KF_SIZE[int(S.loc[t, "inlet_in"])] for t in TAGS}
FW24 = {t: str(S.loc[t, "controller_fw"]).startswith("2.") for t in TAGS}
FIT = {t: V.loc[t, "upstream_fitting"] for t in TAGS}
LD = {t: float(V.loc[t, "straight_run_diameters"]) for t in TAGS}
FLEX_FT = {t: (float(V.loc[t, "flex_length_ft"]) if pd.notna(V.loc[t, "flex_length_ft"]) else None) for t in TAGS}
EAST = {t: S.loc[t, "wing"] == "east" for t in TAGS}
PUNCH_KINKED = re.findall(r"VAV-3-\d\d", open(os.path.join(DATA, "docs", "renovation_2025.md")).read().split(
    "Punch list")[1].split("Commissioning walk-down")[0])


def closed_zero():
    z = {}
    for t in TAGS:
        tr = pd.read_csv(os.path.join(DATA, "trends", "%s.csv" % t.lower()))
        shut = tr[tr.flow_sp_cfm == 0]
        z[t] = float(shut.vp_inwc.median()) if len(shut) >= 20 else None    # None: the box never closes
    return z


def visit(tag):
    """One hood visit, or the report already on disk if this box was visited (a rerun)."""
    done = sorted(glob.glob(os.path.join(VISITS, "visit*_%s.json" % tag)))
    if done:
        return json.load(open(done[0]))
    req = urllib.request.Request(URL.rstrip("/") + "/visit?box=" + tag, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def fit_visit(rec):
    vp = np.array([p["vp_inwc"] for p in rec["points"]], float)
    q = np.array([p["hood_total_cfm"] for p in rec["points"]], float)
    A = np.vstack([vp, -np.ones_like(vp)]).T          # q^2 = K^2 vp - K^2 off
    w = 1.0 / q                                        # q^2 errors grow with q: weight toward low flows
    c = np.linalg.lstsq(A * w[:, None], q ** 2 * w, rcond=None)[0]
    return math.sqrt(c[0]), c[1] / c[0]


def decay_fit(ld, m, sign):
    ld, m = np.asarray(ld, float), np.asarray(m, float)
    s = least_squares(lambda z: 1 + sign * z[0] * np.exp(-ld / z[1]) - m, [0.2, 1.5], bounds=([0, 0.2], [1.0, 6.0]))
    return s.x


def main():
    z = closed_zero()
    off = {}
    for t in TAGS:
        if z[t] is not None and (FW24[t] or abs(z[t]) > HEALTHY_ZERO):
            off[t] = z[t]
        else:
            off[t] = 0.0

    def cls(t):
        f = FIT[t]
        if f.startswith("straight"):
            return "straight"
        if "elbow" in f:
            return "elbow_v" if "vertical" in f else "elbow_h"
        if t in PUNCH_KINKED:
            return "kinked"
        if FLEX_FT[t] is not None and FLEX_FT[t] > 5.0:
            return "sagging"
        return "flex"

    C = {t: cls(t) for t in TAGS}
    labs24 = [t for t in TAGS if FW24[t] and z[t] is None]
    plan = list(labs24)
    covered = {C[t] for t in plan}
    for c, pick in (("elbow_v", lambda ts: min(ts, key=lambda t: LD[t])),
                    ("sagging", lambda ts: max(ts, key=lambda t: FLEX_FT[t]))):
        members = [t for t in TAGS if C[t] == c and EAST[t]]
        if members and c not in covered:
            plan.append(pick(members))
            covered.add(c)
    assert len(plan) <= 5, plan

    meas = {}
    for t in plan:
        K, o = fit_visit(visit(t))
        meas[t] = (K, o)

    m = {t: meas[t][0] / KF[t] for t in meas}
    for t in R.index:
        if EAST[t] or t in m:
            continue                                    # east-wing readings predate the re-ducting
        z24 = 0.5 * off[t] if FW24[t] else 0.0
        vp = (R.loc[t, "bas_cfm"] / KF[t]) ** 2 - z24
        m[t] = R.loc[t, "hood_cfm"] / (KF[t] * math.sqrt(vp))

    eh = [t for t in m if C[t] == "elbow_h"]
    a_h, lam_h = decay_fit([LD[t] for t in eh], [m[t] for t in eh], -1)
    def amplitude(ts):               # one-parameter least squares at the elbows' decay length
        x = np.array([math.exp(-LD[t] / lam_h) for t in ts]); y = np.array([m[t] - 1 for t in ts])
        return float(x @ y / (x @ x))
    a_f = amplitude([t for t in m if C[t] == "flex"])
    a_v = amplitude([t for t in m if C[t] == "elbow_v"])
    kink = np.mean([m[t] for t in m if C[t] == "kinked"])
    sag = np.mean([m[t] for t in m if C[t] == "sagging"])
    model = dict(straight=lambda t: 1.0,
                 elbow_h=lambda t: 1 - a_h * math.exp(-LD[t] / lam_h),
                 elbow_v=lambda t: 1 + a_v * math.exp(-LD[t] / lam_h),
                 flex=lambda t: 1 + a_f * math.exp(-LD[t] / lam_h),
                 kinked=lambda t: kink, sagging=lambda t: sag)

    rows = []
    for t in TAGS:
        if t in meas:
            K, o = meas[t]
        else:
            K, o = KF[t] * (m[t] if t in m else model[C[t]](t)), off[t]
        rows.append((t, round(K, 1), round(o, 4)))
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag", "k_factor", "vp_offset_inwc"])
        w.writerows(rows)
    print("visited:", plan)
    print("classes: horizontal elbow a=%.3f lam=%.2f D | flex a=%.3f | vertical a=%.3f | kinked %.3f | sagging %.3f"
          % (a_h, lam_h, a_f, a_v, kink, sag))
    print("offsets from closed-damper VP:", {t: round(off[t], 4) for t in TAGS if off[t] and t not in meas})


if __name__ == "__main__":
    main()
