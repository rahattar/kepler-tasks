"""Writes the agent-visible records of cooling tower CT-2 from cells.py.  python3 gen.py OUT_DIR"""
import os, shutil, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cells as K
HERE = os.path.dirname(os.path.abspath(__file__))


def main(out):
    os.makedirs(out, exist_ok=True)
    rec, met = K.simulate()
    rec = rec.copy(); rec["time"] = rec.time.dt.strftime("%Y-%m-%d %H:%M")
    cols = ["time"]
    for c in K.CELLS:
        cols += [c + "_flow", c + "_fan_pct", c + "_fan_kw", c + "_hw_in_c", c + "_cw_out_c"]
    cols += ["header_flow_m3h"]
    rec = rec[cols].rename(columns={c + "_flow": c + "_riser_flow" for c in K.CELLS})
    rec.to_csv(os.path.join(out, "dcs_hourly.csv"), index=False)
    met = met.copy(); met["time"] = met.time.dt.strftime("%Y-%m-%d %H:%M")
    met.rename(columns={"time": "timestamp"}).to_csv(os.path.join(out, "met_station.csv"), index=False)
    tags = []
    for c in K.CELLS:
        unit = "US gpm" if c in K.GPM_CELLS else "m3/h"
        tags += [(c + "_riser_flow", "riser flowmeter, cell %s" % c, unit),
                 (c + "_fan_pct", "fan VFD speed reference, cell %s" % c, "% of full speed"),
                 (c + "_fan_kw", "fan motor input power, cell %s (power transducer at the MCC)" % c, "kW"),
                 (c + "_hw_in_c", "hot water temperature in the cell riser above the distribution header tee, cell %s" % c, "degC"),
                 (c + "_cw_out_c", "cold water temperature at the cell's basin outlet weir, cell %s" % c, "degC")]
    tags.append(("header_flow_m3h", "hot water supply header flowmeter (feeds the eight risers and the C1 freeze-protection bypass)", "m3/h"))
    pd.DataFrame(tags, columns=["tag", "description", "unit"]).to_csv(os.path.join(out, "dcs_tags.csv"), index=False)
    log = [("2026-03-30", "C1", "Freeze-protection bypass valve opened for the spring start-up"),
           ("2026-04-14", "C1", "Freeze-protection bypass valve closed"),
           ("2026-05-02", "C5", "Drift eliminator panels washed"),
           ("2026-06-15", "C4", "Fan motor replaced after a bearing failure (spare motor from stores)"),
           ("2026-07-06", "C3", "Riser isolation valve shut and blind flange fitted, fan locked out, basin drained: cell out of service for fill replacement (new film fill, same type as design)"),
           ("2026-07-20", "C3", "Cell returned to service with new fill (blind flange removed, riser valve reopened 14:00)"),
           ("2026-06-24", "C8", "Fan stack extended by 2.4 m (vendor upgrade kit); fan back in service 15:00"),
           ("2026-06-20", "C2", "Hot water thermocouple TE-2H replaced (old one noisy)"),
           ("2026-09-28", "C1", "Inspection: freeze-protection bypass valve found passing; replacement valve ordered for the October outage")]
    log.sort(key=lambda r: r[0])
    pd.DataFrame(log, columns=["date", "cell", "entry"]).to_csv(os.path.join(out, "maintenance_log.csv"), index=False)
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    for n in sorted(os.listdir(os.path.join(HERE, "docs"))):
        txt = open(os.path.join(HERE, "docs", n)).read()
        txt = (txt.replace("C_DESIGN", "%.4f" % K.C_DESIGN).replace("G_DESIGN", "%.1f" % K.G_DESIGN)
                  .replace("L_DESIGN", "%.1f" % K.L_DESIGN).replace("RHO_DESIGN", "%.4f" % K.RHO_DESIGN))
        open(os.path.join(out, "docs", n), "w").write(txt)


if __name__ == "__main__":
    main(sys.argv[1])
