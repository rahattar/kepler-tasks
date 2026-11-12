"""A reference route for the bare core, from the agent's files and the laser reports only."""
import csv, os, subprocess, sys
ALPHA = 11.5e-6
def rd(p): return list(csv.DictReader(open(p)))
def f(x): return float(x)

def solve(app, visits=("TP-301A", "TP-301B", "TP-301C", "GF-401", "P-102A"), order=True, fallback=None):
    """fallback: dict of overrides for the study of wrong routes."""
    fb = fallback or {}
    D = os.path.join(app, "data")
    reg = {r["tag"]: r for r in rd(D + "/train_register.csv")}
    sheets = rd(D + "/dial_sheets.csv"); crib = rd(D + "/tool_crib_log.csv")
    cards = {(r["kit"], int(r["bar_set"])): -f(r["mandrel_bottom_reading_mm"]) / 2 for r in rd(D + "/sag_cards.csv")}
    temps = {r["tag"]: r for r in rd(D + "/support_temperatures.csv")}
    oem = {r["model"]: (f(r["rise_mm"]), f(r["lateral_mm"])) for r in rd(D + "/gearbox_running_position.csv")}
    if order:
        for v in visits:
            if not os.path.exists(os.path.join(app, "laser_reports", v + ".csv")):
                subprocess.run([os.path.join(app, "laservisit"), v], check=True, stdout=subprocess.DEVNULL)
    laser = {}
    for v in visits:
        p = os.path.join(app, "laser_reports", v + ".csv")
        if os.path.exists(p):
            laser[v] = {r["quantity"]: f(r["mm"]) for r in rd(p)}

    def kit(s): return [c["kit"] for c in crib if c["issued_to"] == s["fitter"] and c["out"] <= s["date"] <= c["returned"]][0]
    def bar(s): return 1 if f(s["span_mm"]) <= 160 else (2 if f(s["span_mm"]) <= 320 else 3)
    def key(s):
        k, b = kit(s), bar(s)
        if k == "B" and b in (2, 3):
            return (k, b, "old" if s["date"] < "2026-10-15" else "new")
        return (k, b, "")
    sag = {(k, b, ""): v for (k, b), v in cards.items() if not (k == "B" and b in (2, 3))}
    sag[("B", 2, "old")] = cards[("B", 2)]; sag[("B", 3, "old")] = cards[("B", 3)]
    by_tag = {}
    for s in sheets: by_tag.setdefault(s["tag"], []).append(s)
    # a train read twice, untouched between, with one set of known sag: the other set's sag follows
    for tag, ss in by_tag.items():
        if len(ss) == 2 and not fb.get("no_repeat"):
            known = [s for s in ss if key(s) in sag]; unk = [s for s in ss if key(s) not in sag]
            if known and unk:
                a, c = known[0], unk[0]
                d1 = (f(a["SM_bottom"]) - f(c["SM_bottom"])) / 2; d2 = (f(a["MS_bottom"]) - f(c["MS_bottom"])) / 2
                sag[key(c)] = sag[key(a)] + (d1 + d2) / 2
    # a laser visit on a train read with a set of unknown sag
    for tag, L in laser.items():
        for s in by_tag[tag]:
            if key(s) not in sag:
                s1 = -f(s["SM_bottom"]) / 2 - L["y_movable_plane"]; s2 = L["y_stationary_plane"] - f(s["MS_bottom"]) / 2
                sag[key(s)] = (s1 + s2) / 2
    gear_now = dict(oem)
    for tag, L in laser.items():
        if "GR-450" in reg[tag]["stationary_machine"]:
            gear_now["GR-450"] = (L["stationary_rise"], L["stationary_lateral"])
    if "GR-450" in gear_now and gear_now["GR-450"] == oem["GR-450"] and "gear" in fb:
        gear_now["GR-450"] = fb["gear"]
    out = {}
    for tag, r in reg.items():
        ss = sorted(by_tag[tag], key=lambda s: (key(s) not in sag, s["date"]))
        s = ss[0]; k = key(s)
        sg = sag.get(k, fb.get("sag", {}).get(k[:2], 0.0))
        span, a, b = f(s["span_mm"]), f(r["hub_plane_to_front_feet_mm"]), f(r["front_to_rear_feet_mm"])
        ym = -f(s["SM_bottom"]) / 2 - sg; zm = (f(s["SM_right"]) - f(s["SM_left"])) / 2
        ys = f(s["MS_bottom"]) / 2 + sg; zs = (f(s["MS_left"]) - f(s["MS_right"])) / 2
        if tag in laser:
            L = laser[tag]; ys, ym, zs, zm = L["y_stationary_plane"], L["y_movable_plane"], L["z_stationary_plane"], L["z_movable_plane"]
        amb = f(s["ambient_C"]); t = temps[tag]
        g = lambda h, T: ALPHA * f(h) * (f(T) - amb)
        stat = r["stationary_machine"]
        if stat.startswith("gearbox"):
            sr, sl = gear_now[stat.split()[1]]
        else:
            sr, sl = g(r["stationary_shaft_height_mm"], t["stationary_support_running_C"]), 0.0
        if r["movable_machine"] == "steam turbine":
            if tag in laser: mr, ml = laser[tag]["movable_rise"], laser[tag]["movable_lateral"]
            else: mr, ml = fb.get("turb", {}).get(tag, (g(r["movable_shaft_height_mm"], t["movable_support_running_C"]), 0.0))
        else:
            mr, ml = g(r["movable_shaft_height_mm"], t["movable_support_running_C"]), 0.0
        cv, ch = mr - sr, ml - sl
        at = lambda x, p, q: p + (q - p) * x / span
        xf, xr = span + a, span + a + b
        out[tag] = (-(at(xf, ys, ym) + cv), -(at(xr, ys, ym) + cv), -(at(xf, zs, zm) + ch), -(at(xr, zs, zm) + ch))
    return out, sag

def write(app, moves):
    os.makedirs(os.path.join(app, "output"), exist_ok=True)
    with open(os.path.join(app, "output", "moves.csv"), "w") as fh:
        fh.write("tag,v_front_mm,v_rear_mm,h_front_mm,h_rear_mm\n")
        for tag in sorted(moves): fh.write(tag + "," + ",".join("%.3f" % v for v in moves[tag]) + "\n")

if __name__ == "__main__":
    app = sys.argv[1]; mv, sag = solve(app); write(app, mv)
    print({k: round(v, 3) for k, v in sorted(sag.items())})
