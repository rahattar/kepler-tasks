"""What each uncovered class costs under every natural fallback, and the reference's margin."""
import model as M
T = M.build()
def moves_with(t, ds=0.0, stat=None, mov=None):
    """Moves a solver makes if its sag is ds too small (true minus assumed) and it assumes the given running figures."""
    sr, sl, mr, ml = M.running_change(t)
    if stat: sr, sl = stat
    if mov: mr, ml = mov
    ys, ym = t["ys"] - ds, t["ym"] + ds        # reading y_S = B/2 + s_assumed, y_M = -B/2 - s_assumed
    D, a, b = t["span"], t["a"], t["b"]; xf, xr = D + a, D + a + b
    at = lambda x, p, q: p + (q - p) * x / D
    return (-(at(xf, ys, ym) + mr - sr), -(at(xr, ys, ym) + mr - sr), -(at(xf, t["zs"], t["zm"]) + ml - sl), -(at(xr, t["zs"], t["zm"]) + ml - sl))
cls = {}
for t in T.values():
    k = (t["kit"], M.bar_for(t["span"]), t["date"] < M.B_REPLACED)
    cls.setdefault(k, []).append(t)
known = {"A1": .02, "A2": .05, "A3": .11, "B1": .03, "C2": .19}
print("sag classes left uncovered: trains failing / trains in class, by assumed sag")
for k, name in ((("B", 2, False), "B2"), (("B", 3, False), "B3"), (("C", 1, False), "C1"), (("C", 1, True), "C1"), (("C", 3, False), "C3"), (("C", 2, False), "C2")):
    true = M.SAG[k[:2]]
    cands = {"none": 0.0, "mean known": sum(known.values()) / 5}
    cands.update({"as " + n: v for n, v in known.items() if n != name})
    if k[0] == "B": cands["old card"] = M.SAG_B_OLD[k[1]]; cands["B1 x A ratio"] = .03 * (M.SAG[("A", k[1])] / .02)
    if k[0] == "C" and k[1] != 2:
        cands["C2 x A ratio"] = .19 * M.SAG[("A", k[1])] / .05; cands["C2 x old B ratio"] = .19 * ({1: .03, 3: .10}[k[1]]) / .05
        cands["C2 cube law"] = .19 * ({1: 140, 3: 380}[k[1]] / 250.0) ** 3
    row = []
    for n, v in cands.items():
        bad = sum(not M.passes(t, moves_with(t, ds=true - v)) for t in cls[k])
        row.append("%s %.3f: %d" % (n, v, bad))
    print("  %s true %.2f, %d trains | " % (name, true, len(cls[k])) + "; ".join(row))
print("GR-450 left uncovered:")
g = [t for t in T.values() if t["kind"] == "gear"]
for n, v in (("maker's figure", M.GEAR_OEM["GR-450"]), ("GR-800 figure", M.GEAR_OEM["GR-800"]), ("none", (0, 0)),
             ("growth formula", None)):
    bad = 0
    for t in g:
        vv = v if v else (M.growth(t["h_stat"], t["t_stat"], t["amb"]), 0.0)
        bad += not M.passes(t, moves_with(t, stat=vv))
    print("  %-16s %d of %d fail" % (n, bad, len(g)))
print("a turbine left unvisited:")
for tag in sorted(M.TURB_NOW):
    t = T[tag]; row = []
    for n, v in [("2023 hot check", M.TURB_2023[tag]), ("growth formula", (M.growth(t["h_mov"], t["t_mov"], t["amb"]), 0.0))] + \
                [("as " + o, M.TURB_NOW[o]) for o in sorted(M.TURB_NOW) if o != tag] + \
                [("2023 scaled by " + o, tuple(M.TURB_2023[tag][i] * M.TURB_NOW[o][i] / M.TURB_2023[o][i] for i in (0, 1))) for o in sorted(M.TURB_NOW) if o != tag]:
        r = M.residual(t, moves_with(t, mov=v))
        row.append("%s: %s (%.2f, %.2f)" % (n, "FAILS" if not M.passes(t, moves_with(t, mov=v)) else "passes", r[0], r[2]))
    print("  %s | " % tag + "; ".join(row))
