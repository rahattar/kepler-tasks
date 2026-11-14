import sys, time, numpy as np
sys.path.insert(0, '.')
import ehl

def dh(c):  # Dowson-Higginson h_min
    return 2.65 * c.U ** 0.7 * c.G ** 0.54 * c.W ** -0.13 * c.R
def ph_c(c):  # Pan-Hamrock 1989 central and minimum
    return 2.922 * c.W ** -0.166 * c.U ** 0.692 * c.G ** 0.470 * c.R, 1.714 * c.W ** -0.128 * c.U ** 0.694 * c.G ** 0.568 * c.R

R, Ep, eta0, alpha = 0.01, 2.27e11, 0.02, 2.0e-8
cases = [(5e5, 5.0), (1.0e6, 2.0), (1.5e6, 1.0), (2.0e6, 0.5), (2.0e6, 0.2)]
for w, um in cases:
    mk = lambda f, w=w, um=um: ehl.Case(w * f, R, Ep, eta0, alpha, um)
    c = mk(1.0)
    row = []
    for N in (500, 1000, 2000):
        t = time.time()
        # continuation in load from 20 per cent of the target
        steps = [0.2, 0.35, 0.5, 0.7, 0.85, 1.0]
        out = ehl.continuation(mk, steps, N=N, iters=80)
        s = out[-1][1]
        row.append((N, s["converged"], s.get("Hmin", np.nan), s.get("Hc", np.nan), time.time() - t))
    hmin = [c.h_dim(r[2]) * 1e6 for r in row]
    hc = [c.h_dim(r[3]) * 1e6 for r in row]
    pc, pm = ph_c(c)
    print("w %.1e um %.1f: M %6.1f L %.1f ph %.2f GPa" % (w, um, c.M, c.L, c.ph / 1e9))
    for r, a, b in zip(row, hmin, hc):
        print("    N %4d conv %-5s hmin %.4f um  hc %.4f um  %.1f s" % (r[0], r[1], a, b, r[4]))
    print("    formulas: Dowson-Higginson hmin %.4f (%+.1f%%)  Pan-Hamrock hmin %.4f (%+.1f%%) hc %.4f (%+.1f%%)"
          % (dh(c) * 1e6, 100 * (dh(c) * 1e6 / hmin[-1] - 1), pm * 1e6, 100 * (pm * 1e6 / hmin[-1] - 1), pc * 1e6, 100 * (pc * 1e6 / hc[-1] - 1)))
