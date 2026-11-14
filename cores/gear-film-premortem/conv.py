import sys, time, numpy as np
sys.path.insert(0, '.')
import ehl
R, Ep, eta0, alpha = 0.01, 2.27e11, 0.02, 2.0e-8
def dh(c): return 2.65 * c.U ** 0.7 * c.G ** 0.54 * c.W ** -0.13 * c.R
for w, um in ((2.0e6, 0.5), (1.5e6, 1.0)):
    mk = lambda f, w=w, um=um: ehl.Case(w * f, R, Ep, eta0, alpha, um)
    c = mk(1.0)
    res = {}
    for Xa in (-4.0, -2.5):
        for N in ((1000, 2000, 4000) if Xa == -2.5 else (1000,)):
            t = time.time()
            out = ehl.continuation(mk, [0.2, 0.35, 0.5, 0.7, 0.85, 1.0], N=N, Xa=Xa, iters=80)
            s = out[-1][1]
            hmin = 1e6 * c.h_dim(s.get("Hmin", np.nan))
            res[(Xa, N)] = hmin
            print("M %.0f Xa %.1f N %d conv %s hmin %.5f um (%.0f s)" % (c.M, Xa, N, s["converged"], hmin, time.time() - t), flush=True)
    a, b, d = res[(-2.5, 1000)], res[(-2.5, 2000)], res[(-2.5, 4000)]
    p = np.log(abs(b - a) / abs(d - b)) / np.log(2) if d != b else float("nan")
    ext = d + (d - b) / (2 ** p - 1) if np.isfinite(p) and p > 0 else d
    print("M %.0f: observed order %.2f, extrapolated hmin %.5f um; Dowson-Higginson %.5f (%+.1f%%)" % (c.M, p, ext, 1e6 * dh(c), 100 * (1e6 * dh(c) / ext - 1)), flush=True)
