"""Writes the agent-visible records of boiler B2's secondary superheater from tubes.py.  python3 gen.py OUT_DIR"""
import os, shutil, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tubes as T
HERE = os.path.dirname(os.path.abspath(__file__))


def main(out):
    os.makedirs(out, exist_ok=True)
    h, s, u = T.records()
    h = h.copy(); h["date"] = h.date.dt.strftime("%Y-%m-%d")
    h.to_csv(os.path.join(out, "historian_daily.csv"), index=False)
    s.to_csv(os.path.join(out, "historian_2018_monthly.csv"), index=False)
    u.to_csv(os.path.join(out, "ut_wall_surveys.csv"), index=False)
    pd.DataFrame([dict(element=e, grade=("SA-213 " + T.GRADE[e]), od_mm=T.DO, nominal_wall_mm=T.H0[T.GRADE[e]],
                       inlet_header=T.HEADER[e], design_flux_factor=T.F_MAP[e]) for e in T.ELEMENTS]).to_csv(
        os.path.join(out, "element_register.csv"), index=False)
    log = [("2015-01-01", "all", "Boiler B2 in commercial service; secondary superheater outlet elements E1-E10 with pad thermocouples on the outlet legs in the penthouse"),
           ("2019-01-08", "all", "Historian archive server failure: daily data for 2018 lost; the monthly operating summary for 2018 survives"),
           ("2019-04-16", "all", "Outage: UT wall survey of the outlet-leg crowns"),
           ("2019-07-01", "all", "DCS upgrade and new historian"),
           ("2020-02-10", "E7", "E7 pad thermocouple renewed (the old one read erratically)"),
           ("2021-04-01", "all", "Long retractable soot blower IK-14 added (slagging in the outlet bank)"),
           ("2021-06-20", "E2", "Outlet leg replaced after a leak at a support weld (new SA-213 T22 tube, pad thermocouple refitted)"),
           ("2022-03-01", "E3", "E3 pad thermocouple open circuit; no penthouse access until an outage, not repaired"),
           ("2022-09-12", "all", "Low-NOx burner modification on the two burner corners below E3 and E4"),
           ("2023-04-18", "all", "Outage: UT wall survey of the outlet-leg crowns"),
           ("2023-05-15", "all", "Chemical clean of the superheater (steam-side oxide removed)"),
           ("2023-11-08", "E9", "Outlet leg replaced after a dissimilar-weld crack with a T91 spare from stores (heavier-wall stock; its size was not recorded); pad thermocouple not refitted"),
           ("2024-03-12", "all", "Historian migrated to the corporate platform"),
           ("2024-07-01", "all", "Coal supply changed to the new contract blend"),
           ("2025-01-20", "E6", "E6 pad thermocouple failed (open circuit), not repaired"),
           ("2025-08-04", "E4", "E4 pad thermocouple failed (open circuit), not repaired"),
           ("2026-10-20", "all", "Unit off for the planned outage")]
    pd.DataFrame(log, columns=["date", "element", "entry"]).to_csv(os.path.join(out, "maintenance_log.csv"), index=False)
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    for n in sorted(os.listdir(os.path.join(HERE, "docs"))):
        shutil.copy(os.path.join(HERE, "docs", n), os.path.join(out, "docs", n))


if __name__ == "__main__":
    main(sys.argv[1])
