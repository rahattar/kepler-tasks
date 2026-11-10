"""Writes the agent-visible records of the AHU-3 floor from the sealed definition (vav.py, seed 31): the box
schedule, the inlet survey, the 2024 TAB report and two weeks of 15-minute BAS trends per box. The documents in
environment/data/docs are written by hand and copied as they are.

    python3 gen.py OUT_DIR
"""
import os, sys, math
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vav

SEED = 31
VP_NOISE = 0.0015


def reported(b, vp):
    return vav.K_FACTORY[b["d"]] * math.sqrt(max(vp, 0.0))


def trend(b, rng):
    t = pd.date_range("2026-09-28 00:00", periods=14 * 96, freq="15min")
    rows = []
    K = vav.K_FACTORY[b["d"]]
    for ts in t:
        occ = ts.weekday() < 5 and 6 <= ts.hour < 19
        if b["zone"] == "lab" or occ:
            load = 0.5 + 0.45 * math.sin(math.pi * (ts.hour + ts.minute / 60 - 6) / 13) if occ else 0.0
            load = min(max(load + rng.normal(0, 0.08), 0.0), 1.0)
            sp = b["qmin"] + load * (b["qmax"] - b["qmin"])
            vp = max((sp / K) ** 2, b["drift"]) + rng.normal(0, VP_NOISE)
            q = reported(b, vp)
        else:
            sp = 0.0
            vp = b["drift"] + rng.normal(0, VP_NOISE)
            q = reported(b, vp)
        rows.append((ts.strftime("%Y-%m-%d %H:%M"), round(sp, 0), round(q, 0), round(vp, 4)))
    return pd.DataFrame(rows, columns=["timestamp", "flow_sp_cfm", "flow_cfm", "vp_inwc"])


def main(out):
    rng = np.random.default_rng(SEED + 1000)
    F = vav.make_floor(SEED)
    os.makedirs(os.path.join(out, "trends"), exist_ok=True)
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    sched = pd.DataFrame([dict(tag=b["tag"], zone=b["zone"], inlet_in=b["d"], design_max_cfm=b["qmax"],
                               design_min_cfm=b["qmin"], unoccupied_min_cfm=b["qmin"] if b["zone"] == "lab" else 0,
                               diffusers=b["diffusers"], controller_fw=b["fw"],
                               wing="east" if b["renovated"] else "west") for b in F])
    sched.to_csv(os.path.join(out, "box_schedule.csv"), index=False)
    survey = pd.DataFrame([dict(tag=b["tag"], upstream_fitting={"straight": "straight duct", "elbow": "hard 90 deg elbow, horizontal turn",
                                                                  "elbow_v": "hard 90 deg elbow, vertical drop",
                                                                  "flex": "flex connector"}[b["fit"]],
                                straight_run_diameters=b["ld"],
                                flex_length_ft=b["flex_ft"] if b["flex_ft"] is not None else "",
                                source="2025 renovation as-built" if b["renovated"] else "2023 construction as-built")
                           for b in F])
    survey.to_csv(os.path.join(out, "inlet_survey.csv"), index=False)
    # 2024 TAB report: one-point readings at design maximum, factory K; east-wing boxes measured before re-ducting
    pick = [b for b in F if not b["renovated"]][::2] + [b for b in F if b["renovated"]][:16:3]
    rep = []
    for b in pick:
        if b["renovated"]:            # before the renovation these inlets were long straight runs
            m_old = 1.0 * (1 + b["eps"])
        else:
            m_old = vav.m_inlet(b["fit"], b["ld_eff"], b["d"], b["bend"]) * (1 + b["eps"])
        q_true = b["qmax"] * m_old
        rep.append(dict(tag=b["tag"], date="2024-03-%02d" % (4 + len(rep) // 4), bas_cfm=b["qmax"],
                        hood_cfm=int(round(q_true * (1 + rng.normal(0, 0.02)))), setpoint="design max"))
    pd.DataFrame(rep).to_csv(os.path.join(out, "tab_report_2024.csv"), index=False)
    for b in F:
        trend(b, rng).to_csv(os.path.join(out, "trends", "%s.csv" % b["tag"].lower()), index=False)
    return F


if __name__ == "__main__":
    main(sys.argv[1])
