"""The defective audit routes of route_study, and the sound variations of method_spread.

Each route is the reference audit with exactly one check left out or done the obvious way. The physics, the record
reading, the identification and the referring all come from the shipped reference (`solution/diagnose.py`); only
the orchestration is restated here, so that a route differs from the reference in nothing but its named defect.

Flags, one per layer:

    register_surfaces   keep the register's internal surfaces, ignoring the replacement in the maintenance log
    register_port       keep the register's port conductance, ignoring the trap fitted in the high-vacuum port
    register_seal       keep the register's seal material, ignoring the seal replaced in the maintenance log
    trust_certificate   take every gauge certificate as right, even where the speed it yields is above rated
    latest_speed_test   take the latest speed test whatever the controller rows show since
    commissioning_speed take the commissioning speed test
    no_gas_correction   take the nitrogen-equivalent pressure as the true pressure
    all_entries         use every entry of the log, including those before the internals were replaced
    uncorrected_cathode use the cold cathode readings as they stand, without checking them against the reference
    logged_serials      apply the certificate of the serial the log names, crossed or not
    ignore_vent_gas     treat a dry nitrogen vent as an air vent
    ignore_load         treat every pumpdown as having run empty
    ignore_temperature  take every reading as if the wall had been at 20 C
    table_outgassing    take the outgassing table's nominal gas load instead of identifying the chamber's own
    no_time_reference   take the latest reading as the reference condition, uncorrected for its pumping time
    leak_only           call every residual a constant leak, never a trapped volume
    skip_pump_gate      name the largest gas load and never the pump
    face_value          the register, the latest speed test, the logged serials, every entry, the table's gas load
                        and no correction

Three further flags are not defects but sound variations, used by method_spread:

    drop_oldest         leave out the oldest entry that still describes the chamber, where four or more remain
    median_constant     take the constant part of the gas load as the median of the entries' residuals
    second_speed_test   take the next-to-latest surviving speed test rather than the latest
"""
import contextlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(TASK, "solution"))
import diagnose as D                                                    # noqa: E402

FACE_VALUE = dict(register_surfaces=True, register_port=True, register_seal=True, trust_certificate=True, latest_speed_test=True, logged_serials=True,
                  all_entries=True, uncorrected_cathode=True, no_gas_correction=True, ignore_vent_gas=True,
                  ignore_load=True, ignore_temperature=True, table_outgassing=True, leak_only=True)

VARIATIONS = ["drop_oldest", "median_constant", "second_speed_test"]

ROUTES = ["register_surfaces", "register_port", "register_seal", "trust_certificate", "latest_speed_test", "commissioning_speed", "no_gas_correction",
          "all_entries", "uncorrected_cathode", "logged_serials", "ignore_vent_gas", "ignore_load",
          "ignore_temperature", "table_outgassing", "no_time_reference", "leak_only", "skip_pump_gate",
          "face_value"]


def opts(name=None, **over):
    o = {k: False for k in ROUTES + VARIATIONS}
    if name == "face_value":
        o.update(FACE_VALUE)
        o["face_value"] = True
    elif name:
        o[name] = True
    o.update(over)
    return o


@contextlib.contextmanager
def no_correction():
    """Takes the nitrogen-equivalent pressure as the true pressure, everywhere the reference would correct it."""
    saved = D.gas_correction
    D.gas_correction = lambda parts, seal: 1.0
    try:
        yield
    finally:
        D.gas_correction = saved


# ----------------------------------------------------------------------------------------------------------------
def config_for(cid, data, o):
    cfg = D.chamber_config(cid, data)
    if o["register_surfaces"]:
        reg = [r for r in data["register"] if r["chamber"] == cid]
        cfg["surfaces"] = [(float(r["surface_area_m2"]), r["surface"]) for r in reg]
        cfg["internals_from"] = None
    if o["register_port"]:
        reg = [r for r in data["register"] if r["chamber"] == cid][0]
        cfg["c_port"] = float(reg["c_port_l_s"])
        cfg["trap_from"] = None
    if o["register_seal"]:
        reg = [r for r in data["register"] if r["chamber"] == cid][0]
        cfg["seal"] = reg["seal_material"]
        cfg["seal_cm"] = float(reg["seal_length_cm"])
        cfg["seal_hist"] = [("0000-00-00", cfg["seal"], cfg["seal_cm"])]
    return cfg


def speed_for(cid, cfg, data, o, vac, changed):
    rows = sorted([r for r in data["speed"] if r["chamber"] == cid], key=lambda r: r["date"])
    if o["commissioning_speed"]:
        return float(rows[0]["s_eff_l_s"])
    if o["latest_speed_test"]:
        return float(rows[-1]["s_eff_l_s"])
    if o["second_speed_test"] and not changed:
        ok = [x for x in rows if not (cfg["trap_from"] and x["date"] < cfg["trap_from"])]
        if len(ok) >= 2:
            k = D.certificate_error(cid, cfg, data)
            return float(ok[-2]["s_eff_l_s"]) / k
    k = 1.0 if o["trust_certificate"] else D.certificate_error(cid, cfg, data)
    s, from_gauge = D.ordered_speed(cid, cfg, vac)
    if s is None:
        s, from_gauge = D.surviving_speed(cid, cfg, data, changed), True
    if s is None and changed:
        s, from_gauge = D.baseline_speed(cid, cfg, data, data["certs"],
                                         D.crossed_serials(data, data["certs"]), changed, k), False
    if s is None:
        s, from_gauge = D.series(D.curve(D.TURBO[cfg["turbo"]], 1e-6), cfg["c_port"]), False
    return s / k if from_gauge else s


def points_for(cid, cfg, data, certs, fix, o, changed):
    use_fix = {} if o["logged_serials"] else fix
    look = dict(cfg, internals_from=None) if o["all_entries"] else cfg
    pts = D.entry_points(cid, look, data, certs, use_fix)
    if not o["uncorrected_cathode"]:
        pts = D.correct_drift(pts, cid, data)
    if changed and not (o["latest_speed_test"] or o["commissioning_speed"]):
        pts = [p for p in pts if p["date"] >= changed] or pts
    if o["ignore_vent_gas"]:
        pts = [dict(p, vent="air") for p in pts]
    if o["ignore_load"]:
        pts = [dict(p, load="") for p in pts]
    if o["ignore_temperature"]:
        pts = [dict(p, t_k=D.T_REF) for p in pts]
    if o["drop_oldest"] and len(pts) >= 4:
        # only where the fit keeps slack afterwards: with three entries and two unknowns, dropping one leaves an
        # exactly determined fit and is not something a competent engineer would do
        pts = pts[1:]
    return pts


def identify(cid, cfg, pts, s_eff, data, vac, o):
    rga = D.rga_says(cid, vac)
    if o["table_outgassing"]:
        # the table's nominal gas load, with whatever is left over taken as a leak
        c_w = 1.0
        q = [p["p_n2"] * s_eff for p in pts]
        resid = []
        for i, p in enumerate(pts):
            qq = q[i] * D.gas_correction(
                {"wall-outgassing": D.nominal_wall(cfg, p), "permeation": D.perm_of(cfg, p)}, cfg["seal"])
            resid.append(qq - D.nominal_wall(cfg, p) - D.perm_of(cfg, p))
        q_l = max(sum(resid) / len(resid), 0.0)
        return D.at_reference(cfg, c_w, q_l, 0.0, None)
    if o["no_time_reference"]:
        last = pts[-1]
        c_w, q_l, _qv, _ss, q = D.fit_split(cfg, pts, s_eff)
        qw = c_w * D.nominal_wall(cfg, last)
        qp = D.perm_of(cfg, last)
        parts = {"wall-outgassing": qw, "permeation": qp, "air-leak": max(q[-1] - qw - qp, 0.0),
                 "virtual-leak": 0.0}
        return parts, sum(parts.values())
    if o["median_constant"] and len(D.durations(pts)) >= 2:
        c_w, q_l, _qv, _ss, q = D.fit_split(cfg, pts, s_eff)
        resid = sorted(q[i] - c_w * D.nominal_wall(cfg, p) - D.perm_of(cfg, p) for i, p in enumerate(pts))
        n = len(resid)
        med = resid[n // 2] if n % 2 else 0.5 * (resid[n // 2 - 1] + resid[n // 2])
        trapped = D.best_trapped(cfg, pts, s_eff) if len(pts) >= 3 else None
        if trapped and trapped[3] < 0.25 * _ss:
            return D.at_reference(cfg, trapped[0], trapped[1], trapped[2], trapped[4])
        return D.at_reference(cfg, c_w, max(med, 0.0), 0.0, None)
    if len(D.durations(pts)) >= 2:
        if o["leak_only"]:
            c_w, q_l, _qv, _ss, _q = D.fit_split(cfg, pts, s_eff)
            return D.at_reference(cfg, c_w, q_l, 0.0, None)
        return D.identify_from_log(cid, cfg, pts, s_eff, data, rga)
    if o["leak_only"] and rga is not None:
        pp = rga["pp"]
        q_total = sum(pp.values()) * s_eff
        q_wall_t = (pp.get("h2o", 0.0) + pp.get("h2", 0.0)) * s_eff / D.WALL_WATER
        q_perm_t = D.q_perm(cfg["seal"], cfg["seal_cm"], rga["t_k"])
        nominal = D.q_wall_nominal(cfg["surfaces"], rga["t_h"], "air", rga["t_k"])
        c_w = q_wall_t / nominal if nominal > 0 else 1.0
        return D.at_reference(cfg, c_w, max(q_total - q_wall_t - q_perm_t, 0.0), 0.0, None)
    return D.identify_from_rga(cid, cfg, pts, s_eff, data, rga, vac)


def audit(cid, data, certs, fix, vac, o):
    cfg = config_for(cid, data, o)
    changed = D.pump_changed_on(cid, data)
    s_eff = speed_for(cid, cfg, data, o, vac, changed)
    pts = points_for(cid, cfg, data, certs, fix, o, changed)
    if not o["trust_certificate"]:
        k = D.certificate_error(cid, cfg, data)
        if k != 1.0:
            pts = [dict(q, p_n2=q["p_n2"] * k) for q in pts]
    parts, q_total = identify(cid, cfg, pts, s_eff, data, vac, o)
    s_rated = D.series(D.curve(D.TURBO[cfg["turbo"]], q_total / max(s_eff, 1.0)), cfg["c_port"])
    if not o["skip_pump_gate"] and s_eff < D.PUMP_GATE * s_rated:
        cause = "pump-speed"
    else:
        cause = max(parts, key=lambda k: parts[k])
    return cause, q_total, s_eff


def run(data_dir, vac, name=None, o=None):
    """One route's whole audit sheet, as {chamber: (cause, q_total, s_eff)}."""
    o = o or opts(name)
    data = D.load_data(data_dir)
    certs = data["certs"]
    fix = D.crossed_serials(data, certs)
    ids = sorted({r["chamber"] for r in data["register"]})
    ctx = no_correction() if o["no_gas_correction"] else contextlib.nullcontext()
    with ctx:
        return {cid: audit(cid, data, certs, fix, vac, o) for cid in ids}
