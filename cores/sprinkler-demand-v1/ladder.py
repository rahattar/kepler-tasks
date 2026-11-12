"""Programs that stop short of the reference, to size what each fault costs. Same solver as the reference.

    python3 ladder.py MODE PACKAGE_DIR OUT_JSON

MODE:
  absolute      fits the groups the register leaves open; each gauge taken against the base gauge as written
  as_recorded   the same, with a level for every run and a zero for every gauge
  all_C         every group's C fitted, whatever the register says
  all_C_valves  every group's C and every valve's factor fitted
None of them lets go of the campaign sheet (ports, flows).
"""
import csv
import json
import os
import sys

import ref_rerate as R


def main(mode, pkg_dir, out_path):
    with open(os.path.join(pkg_dir, "system.json")) as f:
        pkg = json.load(f)
    with open(os.path.join(pkg_dir, "campaign.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    S = R.System(pkg)
    camp = R.Campaign(S, rows)
    if mode == "absolute":
        camp.centre = lambda E: E - E[:, [0]]
    if mode in ("all_C", "all_C_valves"):
        camp.var = [("C", i) for i in range(len(S.groups))]
    if mode == "all_C_valves":
        camp.var += [("valve", i) for i in S.valve_pipes]
    camp.x, chi = camp.fit(camp.var, None, None)
    mg, vf = camp.condition(camp.var, camp.x)
    label, P, q = S.search(S.resist(mg, vf))
    with open(out_path, "w") as f:
        json.dump({"area": list(label), "pressure_psi": P, "flow_gpm": q + pkg["hazard"]["hose_gpm"],
                   "fit_chi2": round(chi, 1)}, f)


if __name__ == "__main__":
    main(*sys.argv[1:4])
