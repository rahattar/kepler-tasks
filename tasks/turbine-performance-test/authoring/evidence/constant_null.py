"""Answers that do not reduce the test, against the 0.5 % bound.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import methods as M

T = M.T

if __name__ == "__main__":
    po, ph = T.OUTPUT_MW, T.HEAT_RATE
    print("True values: as_found %.2f MW, %.0f kJ/kWh; as_left %.2f MW, %.0f kJ/kWh"
          % (po["as_found"], ph["as_found"], po["as_left"], ph["as_left"]))
    print("The two conditions differ by %.2f %% in output and %.2f %% in heat rate, so no single pair of values within "
          "0.5 %% satisfies both." % (100 * (po["as_left"] / po["as_found"] - 1), 100 * (ph["as_left"] / ph["as_found"] - 1)))
    raw = dict(no_pt_fix=True, qnh_kept=True, pt102_zero_kept=True, cit_bias_kept=True, fuel_zero_kept=True,
               gc_air_kept=True, whole_run=True)
    d = M.misses(raw)
    ok = sum(abs(v) <= 0.5 for vv in d.values() for v in vv)
    print("The procedure applied to the records as they stand (every logged run averaged, no record fault removed): "
          "%d of 4 values within 0.5 %% (%s)" % (ok, ", ".join("%s %+.2f/%+.2f %%" % (c, v[0], v[1]) for c, v in d.items())))
