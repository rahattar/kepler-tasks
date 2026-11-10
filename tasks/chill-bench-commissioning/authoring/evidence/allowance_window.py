"""How much coefficient error does the dwell allowance tolerate?

This is the measurement that set the allowance at 8%.

In the jump-distance form every station's gap conductance depends on helium pressure P
and accommodation coefficient a only through P * f(a), f(a) = a/(2 - a). The whole
cooldown, and so the optimum dwell, is therefore the same for every coefficient; the
coefficient only decides WHICH pressure realises it, and an error in the coefficient is
exactly an error in pressure. A solver who knows the dwell can be set independently of
the coefficient is left with one question per station: is the pressure inside the band
that, at that dwell, both reaches the target and clears the zone limit?

So the allowance is really a tolerance on the coefficient. For each allowance this
script fixes the dwell at the station's optimum x (1 + allowance - 1.5%), finds the
feasible pressure band at the TRUE coefficient, and converts half its log-width into
the coefficient error a recipe centred in that band can absorb, in each direction.
station_windows.py does the same at the shipped allowance for all sixteen stations.

    python3 allowance_window.py
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import grade
import physics as ph
sys.path.insert(0, HERE)
import station_windows as sw

ALLOWANCES = (0.20, 0.12, 0.08, 0.06)
MARGIN = 0.015
STATIONS = ("S05", "S09", "S07")     # lowest coefficient, plateau corner, highest


def main():
    with open(os.path.join(ROOT, "tests", "truth.json")) as f:
        truth = json.load(f)
    spec = truth["spec"]
    sts = {s.name: s for s in grade._stations(truth)}
    print(__doc__.split("\n\n")[0])
    print("\ndwell fixed at optimum x (1 + allowance - %.1f%%); recipe centred in the "
          "pressure band;\neach cell: how far LOW / HIGH the coefficient estimate may "
          "sit\n" % (100 * MARGIN))
    print("  station  alpha    P_opt   t_opt  | " +
          "  ".join("  allow %3d%%  " % round(100 * a) for a in ALLOWANCES))
    for name in STATIONS:
        st = sts[name]
        a = st.alpha_wafer
        p_opt, t_opt = ph.fastest_feasible(st, 50.0, 25.0, 3.0, 60.0)[:2]
        cells = []
        for allow in ALLOWANCES:
            p_low, p_high, _ = sw.band(st, t_opt * (1.0 + allow - MARGIN), p_opt, spec,
                                       lo=0.45, hi=1.03, n=900)
            if not (np.isfinite(p_low) and np.isfinite(p_high)) or p_high <= p_low:
                cells.append("     none     ")
                continue
            w = 0.5 * np.log(p_high / p_low)
            ff = sw.f(a)
            lo_a = 2 * ff * np.exp(-w) / (1 + ff * np.exp(-w))
            hi_a = 2 * ff * np.exp(w) / (1 + ff * np.exp(w))
            cells.append(" -%4.1f%%/+%4.1f%% " % (100 * (1 - lo_a / a), 100 * (hi_a / a - 1)))
        print("  %-6s   %.4f  %6.2f  %6.3f  |%s" % (name, a, p_opt, t_opt, "".join(cells)),
              flush=True)
    print("\nThe tolerance scales almost linearly with the allowance. At 20% any covariate")
    print("model that gets the shape roughly right lands inside it; at 8% the station")
    print("coefficient has to be known to within about six percent, which is the scale on")
    print("which the prediction errors of competent eight-run campaigns actually lie")
    print("(design_mc.txt, baselines.txt). The highest-coefficient stations are the least")
    print("tolerant, because d ln f / d ln a = 2/(2 - a) grows with the coefficient. At 6%")
    print("the reference's 1.5% margin against its own optimum estimate is already a")
    print("quarter of the allowance.")


if __name__ == "__main__":
    main()
