"""A reference route for v2, from the agent's files and the laser reports only."""
import csv, os, subprocess, sys
ALPHA = 11.5e-6; REF = 25.0
def rd(p): return list(csv.DictReader(open(p)))
f = float

def solve(app, visits=("TP-301A", "TP-301B", "P-301A", "P-320A", "P-322", "P-340A"), mode="full", fine=True):
    """mode: full | record (survey values as they stand) | ratio (2019 ratio at today's temperature, changed pumps too)"""
    D = os.path.join(app, "data")
    reg = {r["tag"]: r for r in rd(D + "/train_register.csv")}
    sheets = {r["tag"]: r for r in rd(D + "/dial_sheets.csv")}; crib = rd(D + "/tool_crib_log.csv")
    cards = {(r["kit"], int(r["bar_set"])): -f(r["mandrel_bottom_reading_mm"]) / 2 for r in rd(D + "/sag_cards.csv")}
    surv = {r["tag"]: r for r in rd(D + "/support_temperature_survey.csv")}
    now = {r["tag"]: f(r["pumped_temperature_C"]) for r in rd(D + "/process_conditions.csv")}
    pump = {r["model"]: (r["casing_support"], r["bearing_pedestal"]) for r in rd(D + "/pump_data.csv")}
    oem = {r["model"]: (f(r["rise_mm"]), f(r["lateral_to_right_mm"])) for r in rd(D + "/gearbox_running_position.csv")}
    change = {}
    for w in rd(D + "/work_orders.csv"):
        if "lagged to PP-2" in w["work"]: change.setdefault(w["item"], set()).add("lag")
        if "cooling water supply and return blanked" in w["work"]: change.setdefault(w["item"], set()).add("dry")
    if not all(os.path.exists(os.path.join(app, "laser_reports", v + ".csv")) for v in visits):
        subprocess.run([os.path.join(app, "laservisit")] + list(visits), check=True, stdout=subprocess.DEVNULL)
    laser = {v: {r["quantity"]: f(r["mm"]) for r in rd(os.path.join(app, "laser_reports", v + ".csv"))} for v in visits}
    def cls(tag):
        st = reg[tag]["stationary_machine"]
        if not st.startswith("pump"): return None
        k19 = (f(surv[tag]["stationary_support_C"]) - REF) / (f(surv[tag]["pumped_temperature_C"]) - REF)
        return (pump[st.split()[1]], tuple(sorted(change.get(tag, ()))), round(k19 / 0.045) if fine else 0)
    ratio = {}
    for tag, L in laser.items():
        c = cls(tag)
        if c and c[1] and mode == "full":
            amb = f(sheets[tag]["ambient_C"])
            ts = amb + L["stationary_rise"] / (ALPHA * f(reg[tag]["stationary_shaft_height_mm"]))
            ratio[c] = (ts - REF) / (now[tag] - REF)
    out = {}
    for tag, r in reg.items():
        s = sheets[tag]
        kit = [c["kit"] for c in crib if c["issued_to"] == s["fitter"] and c["out"] <= s["date"] <= c["returned"]][0]
        span = f(s["span_mm"]); sg = cards[(kit, 1 if span <= 160 else (2 if span <= 320 else 3))]
        a, b = f(r["hub_plane_to_front_feet_mm"]), f(r["front_to_rear_feet_mm"])
        ym = -f(s["SM_bottom"]) / 2 - sg; zm = (f(s["SM_right"]) - f(s["SM_left"])) / 2
        ys = f(s["MS_bottom"]) / 2 + sg; zs = (f(s["MS_left"]) - f(s["MS_right"])) / 2
        amb = f(s["ambient_C"]); sv = surv[tag]
        g = lambda h, T: ALPHA * f(h) * (T - amb)
        st = r["stationary_machine"]
        if st.startswith("gearbox"): sr, sl = oem[st.split()[1]]
        else:
            ts = f(sv["stationary_support_C"])
            if st.startswith("pump") and mode != "record":
                k = (ts - REF) / (f(sv["pumped_temperature_C"]) - REF)
                c = cls(tag)
                if c in ratio: k = ratio[c]
                ts = REF + k * (now[tag] - REF)
            sr, sl = g(r["stationary_shaft_height_mm"], ts), 0.0
        mr, ml = g(r["movable_shaft_height_mm"], f(sv["movable_support_C"])), 0.0
        if tag in laser:
            L = laser[tag]; ys, ym, zs, zm = L["y_stationary_plane"], L["y_movable_plane"], L["z_stationary_plane"], L["z_movable_plane"]
            sr, sl, mr, ml = L["stationary_rise"], L["stationary_lateral"], L["movable_rise"], L["movable_lateral"]
        cv, ch = mr - sr, ml - sl
        at = lambda x, p, q: p + (q - p) * x / span
        xf, xr = span + a, span + a + b
        out[tag] = (-(at(xf, ys, ym) + cv), -(at(xr, ys, ym) + cv), -(at(xf, zs, zm) + ch), -(at(xr, zs, zm) + ch))
    return out, ratio

def write(app, moves):
    os.makedirs(os.path.join(app, "output"), exist_ok=True)
    with open(os.path.join(app, "output", "moves.csv"), "w") as fh:
        fh.write("tag,v_front_mm,v_rear_mm,h_front_mm,h_rear_mm\n")
        for tag in sorted(moves): fh.write(tag + "," + ",".join("%.3f" % v for v in moves[tag]) + "\n")
