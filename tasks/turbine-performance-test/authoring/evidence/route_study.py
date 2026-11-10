"""Wrong side of the 0.5 % bound: the reference with one record trap fallen into at a time.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import methods as M

TRAPS = [
    ("reference", {}),
    ("JT-001 taken as scaled (14400:120 PTs)", dict(no_pt_fix=True)),
    ("DCS generator MW instead of JT-001", dict(dcs_mw=True)),
    ("unit net MW instead of gross", dict(net_mw=True)),
    ("day-2 barometer taken as station pressure", dict(qnh_kept=True)),
    ("PT-102 zero error not removed", dict(pt102_zero_kept=True)),
    ("PT-102 zeroed on the barometer each day", dict(pt102_per_day=True)),
    ("day-2 inlet RTD array bias not removed", dict(cit_bias_kept=True)),
    ("FT-301 zero error not removed", dict(fuel_zero_kept=True)),
    ("air-contaminated gas sample kept", dict(gc_air_kept=True)),
    ("laboratory gross volumetric CV used as LHV", dict(hhv_volumetric=True)),
    ("whole logged runs averaged (A2 disturbance, L3)", dict(whole_run=True)),
    ("run L3 kept", dict(l3_kept=True)),
    ("filter differential pressure as the inlet loss", dict(filter_dp=True)),
    ("fuel temperature at the meter (TE-301)", dict(te301=True)),
]

if __name__ == "__main__":
    print("Miss in percent, (output, heat rate) per condition; the bound is 0.5 %.\n")
    worst = []
    for name, o in TRAPS:
        d = M.misses(o)
        w = max((abs(v) for vv in d.values() for v in vv))
        print("%-50s worst %6.2f   as_found %+6.2f %+6.2f   as_left %+6.2f %+6.2f"
              % (name, w, d["as_found"][0], d["as_found"][1], d["as_left"][0], d["as_left"][1]))
        if o:
            worst.append(w)
    print("\nNearest trap: %.2f %%" % min(worst))
    d = M.misses(dict(no_pf=True))
    print("Not a trap: leaving out the power factor correction moves the results by at most %.2f %%."
          % max(abs(v) for vv in d.values() for v in vv))
