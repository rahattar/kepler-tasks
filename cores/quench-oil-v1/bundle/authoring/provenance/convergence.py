"""How far the sealed definition, at the settings the truth was made with, stands from a much finer solution.

    python3 convergence.py > ../evidence/convergence.txt        (about two minutes)

Thirty-two loads spread over the diameters, steels, temperatures and oils of the sites are cooled twice by
quench.solve: on 64 radial intervals with steps of 1e-4 growing to 1e-3 of R^2 / (6e-6 m2/s), as sites.py
calls it, and on 200 intervals with steps of 2.5e-5 growing to 2.5e-4.
"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quench  # noqa: E402
import sites  # noqa: E402


def main():
    rng = np.random.default_rng(5)
    worst = {name: 0.0 for name in quench.RESULTS}
    count = 0
    for steel in sorted(quench.STEELS):
        n = 16
        d = np.array(sites.DIAMETERS * 2, float)
        furnace = rng.choice(np.arange(830, 881, 5), n).astype(float)
        bath = rng.choice(np.arange(50, 81, 5), n).astype(float)
        kind = rng.choice(sorted(sites.NOMINAL), n)
        f = rng.uniform(0.85, 1.15, n)
        oil = np.array([sites.scaled(sites.NOMINAL[k], x) for k, x in zip(kind, f)], float)
        as_made = quench.solve(steel, d, furnace, bath, oil[:, 0], oil[:, 1], oil[:, 2])
        fine = quench.solve(steel, d, furnace, bath, oil[:, 0], oil[:, 1], oil[:, 2], 200, 2.5e-5, 1.004, 2.5e-4)
        count += n
        for name in quench.RESULTS:
            gap = np.abs(as_made[name] - fine[name])
            if name != "ts_core500_C":
                gap = 100.0 * gap / fine[name]
            worst[name] = max(worst[name], float(gap.max()))
    print("%d loads, the sealed definition as sites.py calls it against 200 intervals and steps a quarter as long" % count)
    for name in quench.RESULTS:
        print("  %-16s largest difference %.3f %s" % (name, worst[name], "K" if name == "ts_core500_C" else "per cent"))
    most = max(v for k, v in worst.items() if k != "ts_core500_C")
    print("largest of the four relative differences: %.3f per cent, which is %.2f of the 1.5 per cent band" % (most, most / 1.5))
    return 0 if most < 0.15 and worst["ts_core500_C"] < 0.3 else 1


if __name__ == "__main__":
    sys.exit(main())
