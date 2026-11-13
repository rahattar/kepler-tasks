import numpy as np, sys, time
from shell import Shell
CLS = [(0, 0), (1, 0), (0, 1), (1, 1)]

def trace(r, nu, H, n=8, steps=60, Qmax=None):
    """pressure against the bow raised in steps along the symmetric path; the load at which the lowest
    eigenvalue of each class first becomes negative (bisected)."""
    s = Shell(r, nu, H, n=n)
    Qmax = Qmax or 60.0 * H ** 2.0 + 40
    z = np.zeros(s.N); Q = 0.0; dQ = Qmax / steps
    first = {}; lam_prev = {c: s.lowest(z, c) for c in CLS}
    hist = []
    while Q < Qmax and len(first) < 4:
        Qn = Q + dQ
        zn = s.newton(-Qn, z)
        if zn is None or abs(s.centre(zn) - s.centre(z)) > 0.6 * max(1.0, H) :      # failed or jumped: symmetric limit
            if dQ > Qmax / steps / 4096:
                dQ /= 2; continue
            first.setdefault((0, 0), Q); break
        lam = {c: s.lowest(zn, c) for c in CLS}
        crossed = [c for c in CLS if c not in first and lam[c] < 0 <= lam_prev[c]]
        if crossed and dQ > Qmax / steps / 512:
            dQ /= 2; continue
        for c in crossed: first[c] = Qn
        z, Q, lam_prev = zn, Qn, lam
        hist.append((Q, s.centre(z)))
        if dQ < Qmax / steps: dQ = min(dQ * 2, Qmax / steps)
    return first, hist

if __name__ == "__main__":
    for r in (1.0, 1.5, 2.0, 3.0):
        for H in (1.5, 2.5, 4.0, 6.0, 8.0):
            t = time.time(); first, hist = trace(r, 0.3, H)
            print("r %.1f H %.1f  " % (r, H) + "  ".join("%s:%8.1f" % ("".join("eo"[p] for p in c), first[c]) if c in first else "%s:    none" % "".join("eo"[p] for p in c) for c in CLS)
                  + "   W at loss %.2f  (%.0fs)" % (hist[-1][1] if hist else 0, time.time() - t), flush=True)
