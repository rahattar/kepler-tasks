"""Sealed truth for the AHU-3 floor: 40 pressure-independent VAV boxes, their flow sensors and the TAB hood.

Controller (all firmware): reported flow Q = K * sqrt(VP - off_user), VP = velocity-pressure reading (in. w.c.).
Firmware 3.x auto-zeroes the transducer hourly (VP carries only a tiny residual); firmware 2.4 does not (VP carries
the transducer drift), and neither does a 3.x box whose auto-zero valve has failed (VAV-3-04, unalarmed). The
factory K assumes a straight inlet of at least 3 diameters.

Truth flow at a sensor reading: Q = K_true * sqrt(VP - drift), K_true = K_factory * m * (1 + eps), with the inlet
multiplier m depending on the upstream fitting, the straight run in diameters (L/D), the inlet size and, for flex
connectors, the bend at the inlet.
"""
import math
import numpy as np

K_FACTORY = {6: 478.0, 8: 850.0, 10: 1328.0, 12: 1912.0, 14: 2603.0}   # cfm per sqrt(in. w.c.)
QMAX_NOM = {6: 400, 8: 700, 10: 1100, 12: 1550, 14: 2100}            # cfm, about 2000 fpm
TOL = 0.10                                                           # +-10 % of setpoint at min and max


def m_inlet(fit, ld, d, bend):
    s = 0.8 + 0.02 * d
    if fit == "elbow":           # horizontal turn into the inlet: the cross reads high, K_true below factory
        return 1.0 - 0.30 * s * math.exp(-ld / 1.2)
    if fit == "elbow_v":         # vertical drop into the inlet: the cross reads low, K_true above factory
        return 1.0 + 0.50 * s * math.exp(-ld / 2.0)
    if fit == "flex":
        g = 0.35 + 0.65 * (bend / 90.0) ** 2
        return 1.0 + 0.40 * s * g * math.exp(-ld / 1.5)
    return 1.0


def make_floor(seed=31):
    rng = np.random.default_rng(seed)
    boxes = []
    # (count, fitting, renovated, L/D range, bend range or None)
    plan = ([("straight", False, (3.0, 8.0))] * 7 + [("elbow", False, (0.6, 5.0))] * 10 + [("flex", False, (1.5, 4.0))] * 3
            + [("straight", True, (3.0, 6.0))] * 4 + [("elbow", True, (0.5, 3.0))] * 5 + [("flex", True, (1.2, 3.5))] * 11)
    sizes = [6, 8, 8, 10, 10, 12, 14, 8, 6, 10]
    for i, (fit, ren, (lo, hi)) in enumerate(plan):
        d = int(sizes[i % len(sizes)] if i % 7 else rng.choice([6, 8, 10, 12, 14]))
        if fit == "elbow" and ren:   # the renovation drops the branch ducts into the east-wing boxes from above
            fit = "elbow_v"
        ld = round(float(rng.uniform(lo, hi)), 1)
        if fit == "elbow_v":         # the drops come off one ceiling main: similar straight runs
            ld = round(1.5 + (ld - lo) / (hi - lo) * 0.6, 1)
        bend = float(rng.uniform(0, 35)) if fit == "flex" else 0.0
        boxes.append(dict(fit=fit, renovated=ren, ld=ld, d=d, bend=bend))
    # kinked flex connectors at three renovated boxes (punch list), one of them a lab box
    kinked = [i for i, b in enumerate(boxes) if b["fit"] == "flex" and b["renovated"]][:: 4][:3]
    for i in kinked:           # crushed at the inlet: the surveyed straight run no longer applies
        boxes[i]["bend"] = float(rng.uniform(75, 90))
        boxes[i]["ld"] = round(float(rng.uniform(1.8, 2.8)), 1)
    # zones: five 24/7 lab boxes in the east wing, the rest offices
    lab = [i for i, b in enumerate(boxes) if b["renovated"]][-5:]
    # firmware 2.4 on nine boxes, three of them labs
    fw24 = sorted(set(lab[:3]) | set(int(x) for x in rng.choice([i for i in range(40) if i not in lab], 6, replace=False)))
    out = []
    for i, b in enumerate(boxes):
        tag = "VAV-3-%02d" % (i + 1)
        qmax = int(round(QMAX_NOM[b["d"]] * rng.uniform(0.82, 1.05) / 10.0) * 10)
        is_lab = i in lab
        qmin = int(round(qmax * (rng.uniform(0.30, 0.38) if is_lab else rng.uniform(0.22, 0.32)) / 5.0) * 5)
        fw = "2.4" if i in fw24 else "3.1"
        drift = float(rng.uniform(0.018, 0.032)) if fw == "2.4" else float(rng.normal(0, 0.0008))
        eps = float(rng.normal(0, 0.010))
        nd = int(np.clip(round(qmax / 260), 1, 8))
        out.append(dict(tag=tag, index=i, zone="lab" if is_lab else "office", d=b["d"], qmax=qmax, qmin=qmin, fw=fw,
                        fit=b["fit"], ld=b["ld"], ld_eff=0.0 if i in kinked else b["ld"], bend=round(b["bend"], 0),
                        renovated=b["renovated"], drift=drift, eps=eps, diffusers=nd, kinked=i in kinked, sag=False,
                        flex_ft=None))
    # revision 3 (separate stream, so the boxes above are unchanged)
    r2 = np.random.default_rng(seed + 77)
    for b in out:
        if b["fit"] == "flex":
            b["flex_ft"] = round(float(r2.uniform(2.0, 4.8)), 1)
    # long unsupported flex runs in the east wing: the connector sags into the inlet
    for tag in ("VAV-3-31", "VAV-3-33", "VAV-3-35"):
        b = out[int(tag[-2:]) - 1]
        b.update(sag=True, flex_ft=round(float(r2.uniform(6.0, 8.0)), 1), bend=60.0, ld_eff=0.5)
    # one firmware 3.1 office box whose auto-zero valve has failed: it keeps an old zero, unalarmed
    stuck = out[3]
    stuck.update(drift=0.026, az_failed=True)
    # lab boxes on firmware 2.4: drifts spread out, lower minimum airflow
    for b, dr, rmin in zip([b for b in out if b["zone"] == "lab" and b["fw"] == "2.4"], (0.040, 0.008, 0.038),
                           (0.30, 0.28, 0.30)):
        b["drift"] = dr
        b["qmin"] = int(round(b["qmax"] * rmin / 5.0) * 5)
    return out


def k_true(b):
    return K_FACTORY[b["d"]] * m_inlet(b["fit"], b["ld_eff"], b["d"], b["bend"]) * (1 + b["eps"])


def true_flow(b, K, off, q_set):
    """True airflow when the controller, configured with (K, off), holds its reported flow at q_set."""
    vp = (q_set / K) ** 2 + off
    vt = vp - b["drift"]
    return k_true(b) * math.sqrt(vt) if vt > 0 else 0.0


def grade(cal, floor):
    """cal: {tag: (K, off)}. Returns per-box worst relative error over min and max and the pass flag."""
    res = {}
    for b in floor:
        if b["tag"] not in cal:
            res[b["tag"]] = dict(err=float("inf"), ok=False)
            continue
        K, off = cal[b["tag"]]
        e = max(abs(true_flow(b, K, off, q) / q - 1) for q in (b["qmin"], b["qmax"]))
        res[b["tag"]] = dict(err=e, ok=e <= TOL)
    return res


def hood_visit(b, k):
    """Readings of visit number k: the box at design minimum, halfway, then design maximum. Each diffuser value is
    the mean of three hood readings (each +-1 % and +-2 cfm, one sigma, the hood's repeatability). The seed depends only on the visit number
    and the box, so the service, the reference and the evidence studies see the same readings for the same plan."""
    rng = np.random.default_rng(5000 + 37 * k + b["index"])
    K = K_FACTORY[b["d"]]
    share = rng.dirichlet(np.full(b["diffusers"], 8.0))
    pts = []
    for name, q in (("design min", b["qmin"]), ("midpoint", round((b["qmin"] + b["qmax"]) / 2.0)), ("design max", b["qmax"])):
        vp = max((q / K) ** 2, b["drift"]) + rng.normal(0, 0.0005)   # damper fully shut if the setpoint is below the zero error
        qt = k_true(b) * math.sqrt(max(vp - b["drift"], 0.0))
        hood = [int(round(np.mean([qt * s * (1 + rng.normal(0, 0.01)) + rng.normal(0, 2) for _ in range(3)])))
                for s in share]
        pts.append(dict(setpoint=name, flow_sp_cfm=q, bas_flow_cfm=round(K * math.sqrt(max(vp, 0.0)), 0),
                        vp_inwc=round(vp, 4), hood_cfm_by_diffuser=hood, hood_total_cfm=int(sum(hood))))
    return pts
