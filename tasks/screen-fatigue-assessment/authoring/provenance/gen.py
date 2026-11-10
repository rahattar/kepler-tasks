"""Writes the agent-visible records of the screen house from the sealed definition (screens.py): register,
maintenance log, daily operating log, strain-record index and records. Documents are written by hand.

    python3 gen.py OUT_DIR
"""
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screens as S

GF_CFG = 2.00
NOISE_UE = 0.2
STEADY_S = 8.0


def to_channels(u, b, sig, when, rng):
    p1, p2 = S.POS[u]
    e1 = sig * (1 - b["g"] * p1) / S.E_MPA * 1e6
    e2 = sig * (1 - b["g"] * p2) / S.E_MPA * 1e6
    k = S.GF_TRUE[u] / GF_CFG
    e1, e2 = e1 * k, e2 * k
    if u == S.DEBOND[0] and when >= pd.Timestamp(S.DEBOND[1]):
        e2 = e2 * S.DEBOND[2]
    if u == S.DEBOND2[0] and when >= pd.Timestamp(S.DEBOND2[1]):
        e1 = e1 * S.DEBOND2[2]
    e1 = e1 + rng.normal(0, NOISE_UE, e1.size)
    e2 = e2 + rng.normal(0, NOISE_UE, e2.size)
    if u == S.SWAPPED:
        e1, e2 = e2, e1
    return e1, e2


def schedule(u, rng):
    """Record times and kinds for one unit."""
    lo = pd.Timestamp("2026-07-02" if u == "S8" else "2026-06-02")
    hi = pd.Timestamp("2026-10-28")
    span = (hi - lo).total_seconds()
    kinds = ["loaded"] * 8 + ["empty"] * 2 + ["start"] * 2 + ["stop"] * 3
    if u == S.DEBOND[0]:          # S1: the campaign ran on into the autumn; most records fall after mid-August
        lo2 = pd.Timestamp("2026-08-24")
        times = [lo + pd.Timedelta(seconds=float(x)) for x in rng.uniform(0, (lo2 - lo).total_seconds(), 5)]
        times += [lo2 + pd.Timedelta(seconds=float(x)) for x in rng.uniform(0, (hi - lo2).total_seconds(), 10)]
    else:
        times = [lo + pd.Timedelta(seconds=float(x)) for x in rng.uniform(0, span, len(kinds))]
    order = rng.permutation(len(kinds))
    out = []
    for t, i in zip(sorted(times), order):
        out.append((t.floor("min"), kinds[i]))
    return out


def main(out):
    bank, log = S.truth()
    S.save_bank(bank, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bank.json"))
    rng = np.random.default_rng(4242)
    os.makedirs(os.path.join(out, "records"), exist_ok=True)
    reg = pd.DataFrame([dict(screen=u, serial="DDS-3073-%03d" % (11 + S.UNITS.index(u)),
                             commissioned=S.COMMISSIONED[u], motor_rpm=int(S.RPM[u]),
                             drive_kw=37 if u in S.FRAME_B else 30, side_plate_mm=int(S.THICK[u]),
                             gusset="rev B" if S.FAT[u] == 100.0 else "rev A") for u in S.UNITS])
    reg.to_csv(os.path.join(out, "screen_register.csv"), index=False)
    pub = log.rename(columns={"unit": "screen"}).copy()
    m = (pub.screen == S.STARTS_DOUBLED[0]) & (pub.date >= S.STARTS_DOUBLED[1])
    pub.loc[m, "starts"] = 2 * pub.loc[m, "starts"]          # pilot historian counts start and stop commands
    gap = (pub.screen == S.GAP[0]) & (pub.date >= S.GAP[1]) & (pub.date <= S.GAP[2])
    G = pub[gap].copy()
    pub = pub[~gap]
    pub.to_csv(os.path.join(out, "operating_log.csv"), index=False)
    G["month"] = G.date.str[:7]
    G["run_h"] = G[S.BAND_COLS].sum(axis=1)
    mon = G.groupby("month").agg(run_h=("run_h", "sum"), h_empty=("h_empty", "sum"), starts=("starts", "sum")).reset_index()
    prod = "\n".join("| %s | %.0f | %.0f | %d |" % (r.month, r.run_h, r.h_empty, r.starts) for r in mon.itertuples())
    idx = []
    n = 0
    for u in S.UNITS:
        b = bank[u]
        for when, kind in schedule(u, rng):
            if u == S.NO_RECORDS or (u in S.NO_EVENTS and kind in ("start", "stop")):
                continue                              # never captured (see the maintenance log)
            n += 1
            rid = "R%04d" % n
            fs = S.FS[u]
            if kind in ("loaded", "empty"):
                F = 0.0 if kind == "empty" else float(np.round(rng.uniform(80, 790)))
                A = float(S.amp(b, F)) * (1 + 0.015 * rng.standard_normal())
                t = np.arange(int(STEADY_S * fs)) / fs
                sig = A * S.wave(2 * np.pi * b["f_op"] * t + rng.uniform(0, 2 * np.pi), b)
            else:
                F = 0.0
                sig, rpm = S.event(b, kind, fs, rng)
            e1, e2 = to_channels(u, b, sig, when, rng)
            cols = {"ch1_ue": np.round(e1, 2), "ch2_ue": np.round(e2, 2)}
            if kind in ("start", "stop"):             # event records also carry the drive's speed signal
                cols["speed_rpm"] = np.round(rpm + rng.normal(0, 0.5, rpm.size), 1)
            pd.DataFrame(cols).to_csv(os.path.join(out, "records", rid.lower() + ".csv"), index=False)
            idx.append(dict(record=rid, screen=u, start=when.strftime("%Y-%m-%d %H:%M"), kind=kind,
                            feed_tph=int(F) if kind == "loaded" else 0, sample_rate_hz=500,
                            file="records/%s.csv" % rid.lower()))
    pd.DataFrame(idx).to_csv(os.path.join(out, "records", "index.csv"), index=False)
    mlog = [(S.COMMISSIONED[u], u, "Commissioned; gusset %s" % ("rev B (redesigned, non-load-carrying)" if S.FAT[u] == 100 else "rev A"))
            for u in S.UNITS]
    mlog += [("2021-10-05", "S2", "Exciter bearings renewed (both shafts); coast-down re-timed after the job: full to half speed %.1f s" % S.TAU_CHANGE[2]),
             ("2025-11-12", "S6", "Crack found at the exciter-beam gusset weld toe, drive side; screen stopped"),
             ("2025-11-14", "S6", "Gusset and adjacent side-plate panel replaced (rev A, like for like); screen returned to service"),
             ("2026-03-02", "S1-S10", "Motor brakes fitted to every screen drive (stop programme after the S6 crack); stops now brake to standstill"),
             ("2026-05-18", "S1-S10", "Strain gauges installed at the monitored gusset weld toes (see gauge installation sheet); loggers fitted"),
             ("2026-05-18", "S5", "Logger fitted but its firmware never armed the recording: no strain records from S5 (found at the October download)"),
             ("2026-05-18", "S4,S6", "Loggers' start/stop trigger inputs left unwired: no event records from S4 or S6 (steady records unaffected)"),
             ("2026-06-03", "S7", "Junction box JB-7 rewired after cable damage by a falling liner"),
             ("2026-07-01", "S8", "Logger failed; replaced with the spare logger from stores"),
             ("2026-10-20", "S9", "Magnetic-particle inspection of the drive-side gusset weld toes during a stop: no indications"),
             ("2026-09-08", "S1", "Gauge G2 protective cover found torn and the gauge wet; cover renewed")]
    mlog.sort(key=lambda r: r[0])
    pd.DataFrame(mlog, columns=["date", "screen", "work_done"]).to_csv(os.path.join(out, "maintenance_log.csv"), index=False)
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    table = "  | screen | full to half speed, s |\n  |---|---|\n" + "\n".join(
        ("  | %s | not timed |" % u) if u in S.UNTIMED else ("  | %s | %.1f |" % (u, bank[u]["tau"] * np.log(2.0)))
        for u in S.UNITS)
    for name in sorted(os.listdir(src)):
        text = open(os.path.join(src, name)).read().replace("COAST_TABLE", table).replace("PROD_TABLE", prod)
        open(os.path.join(out, "docs", name), "w").write(text)
    return bank


if __name__ == "__main__":
    main(sys.argv[1])
