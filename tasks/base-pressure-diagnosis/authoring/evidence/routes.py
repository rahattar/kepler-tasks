"""The defective audit routes of route_study, and the sound variations of method_spread.

Each route is the shipped reference (`solution/diagnose.py`) with exactly one decision left out or done the obvious
way. Nothing of the reference is restated here. A route replaces one or two of the reference's own functions or
constants for the length of one run, through `patched()`, and restores them afterwards; everything else - the
reading, the instruments, the speed, the fit, the choice of budget, the referring - is the reference's code as it
ships. A route cannot drift from the reference, because it is the reference.

An earlier version of this file kept its own copy of the reference's pipeline, which matched the reference only
until the reference changed (the 11 November review).

Routes, one per layer:

    register_surfaces    keep the register's internal surfaces, ignoring the replacement in the maintenance log
    register_port        keep the register's port conductance, ignoring the trap fitted in the high-vacuum port
    register_seal        keep the register's seal, ignoring a seal change the maintenance log records
    trust_register_seal  never set the register's seal material aside, whatever the records show
    trust_certificate    take every gauge certificate as right, even where the speed it yields is above rated
    undated_certificates apply a gauge's latest certificate factor to every reading, whatever its date
    register_pump        take the pump the register names, whatever the controller's own figures report
    latest_speed_test    take the latest speed test whatever the controller rows show since
    commissioning_speed  take the chamber's first speed test
    no_gas_correction    take the nitrogen-equivalent pressure as the true pressure
    all_entries          use every entry of the log, including those before the internals were replaced
    void_before_change   discard every record from before the chamber's last logged work
    uncorrected_cathode  use the cold cathode readings as they stand, without checking them against the reference
    logged_serials       apply the certificate of the serial the log names, crossed or not
    ignore_vent_gas      treat a dry nitrogen vent as an air vent
    ignore_load          treat every pumpdown as having run empty
    ignore_temperature   take every reading as if the wall had been at 20 C
    table_outgassing     take the outgassing table's nominal wall load instead of identifying the chamber's own
    no_time_reference    refer the gas budget to the latest entry's own condition instead of the reference's
    leak_only            never admit a trapped volume
    skip_pump_gate       name the largest gas load and never the pump
    face_value           all of the record-reading routes at once

Sound variations, used by method_spread, each a defensible way of doing the same audit:

    drop_oldest          leave out the oldest entry where four or more remain
    mean_speed_test      take the mean of the period's speed tests rather than the latest
    strict_seal          ask twice the evidence before setting the register's seal aside
    lenient_seal         ask half of it
    equal_weights        weight the ordered test as one more gauge reading
    fine_tau_grid        search the time constant on a grid twice as fine
"""
import contextlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(TASK, "solution"))
import diagnose as D                                                    # noqa: E402

ROUTES = ["register_surfaces", "register_port", "register_seal", "trust_register_seal", "trust_certificate",
          "undated_certificates", "register_pump", "latest_speed_test", "commissioning_speed",
          "no_gas_correction", "all_entries", "void_before_change", "uncorrected_cathode", "logged_serials",
          "ignore_vent_gas", "ignore_load", "ignore_temperature", "table_outgassing", "no_time_reference",
          "leak_only", "skip_pump_gate", "face_value"]

FACE_VALUE = ["register_surfaces", "register_port", "register_seal", "trust_register_seal", "trust_certificate",
              "undated_certificates", "register_pump", "latest_speed_test", "no_gas_correction", "all_entries",
              "uncorrected_cathode", "logged_serials", "ignore_vent_gas", "ignore_load", "ignore_temperature",
              "table_outgassing", "leak_only"]

VARIATIONS = ["drop_oldest", "mean_speed_test", "strict_seal", "lenient_seal", "equal_weights", "fine_tau_grid"]


def opts(name=None, **flags):
    """The names to apply: one route or variation, or several flags (kept for method_spread's call)."""
    out = [name] if name else []
    return out + [k for k, v in flags.items() if v]


# ------------------------------------------------------------------------------------------------ the patches
def _register_row(data, cid):
    return [r for r in data["register"] if r["chamber"] == cid]


def _wrap_config(change):
    orig = D.chamber_config

    def chamber_config(cid, data):
        cfg = orig(cid, data)
        change(cfg, _register_row(data, cid))
        return cfg
    return chamber_config


def _register_surfaces(cfg, reg):
    cfg["surfaces"] = [(float(r["surface_area_m2"]), r["surface"]) for r in reg]
    cfg["internals_from"] = None


def _register_port(cfg, reg):
    cfg["c_port"] = float(reg[0]["c_port_l_s"])
    cfg["trap_from"] = None


def _register_seal(cfg, reg):
    cfg["seal"] = reg[0]["seal_material"]
    cfg["seal_cm"] = float(reg[0]["seal_length_cm"])
    cfg["seal_hist"] = [cfg["seal_hist"][0]]
    cfg["seal_logged_from"] = None


def _all_entries(cfg, reg):
    cfg["internals_from"] = None


def _commissioning_speed(orig):
    def shop_speed_in(cid, data, cuts, period, k):
        rows = sorted([r for r in data["speed"] if r["chamber"] == cid], key=lambda r: r["date"])
        return float(rows[0]["s_eff_l_s"]) / k if rows else None
    return shop_speed_in


def _mean_speed_test(orig):
    def shop_speed_in(cid, data, cuts, period, k):
        rows = [float(r["s_eff_l_s"]) / k for r in data["speed"]
                if r["chamber"] == cid and D.period_of(r["date"], cuts) == period]
        return sum(rows) / len(rows) if rows else None
    return shop_speed_in


def _undated(orig):
    def cert_factor(certs, serial, date):
        return certs[serial][1][-1][1]
    return cert_factor


def _air_vent(orig):
    def q_wall_nominal(surfaces, t_h, vent, t_k):
        return orig(surfaces, t_h, "air", t_k)
    return q_wall_nominal


def _structures(keep):
    orig = D.candidate_structures

    def candidate_structures(cid, cfg, data, obs):
        return [s for s in orig(cid, cfg, data, obs) if keep(s)]
    return candidate_structures


def _table_outgassing(orig):
    """The fit with the wall coefficient held at the table's figure: the leak and any trapped volume take what the
    table's wall load leaves of each observation's gas load."""
    import numpy as np
    from scipy.optimize import nnls

    def fit_budget(cfg, obs, structure, s_now, helium=None):
        chi2, k, params, q = orig(cfg, obs, structure, s_now, helium)
        W = np.array([D.nominal_wall(cfg, o) for o in obs])
        mats = [D._seal_for(cfg, o["date"], structure.get("seal")) for o in obs]
        PM = np.array([D.q_perm(m, cm, o["t_k"]) for (m, cm), o in zip(mats, obs)])
        tf, tau = structure.get("trapped_from"), params["tau"]
        H = np.array([o["t_h"] for o in obs])
        TR = np.array([1.0 if tf is not None and o["date"] >= tf else 0.0 for o in obs])
        w = 1.0 / (np.asarray(q) * np.array([o["sd"] for o in obs]))
        cols = [np.ones(len(obs))] + ([TR * np.exp(-H / tau)] if tau else [])
        x, rn = nnls(np.column_stack(cols) * w[:, None], (np.asarray(q) - PM - W) * w)
        p = dict(params, c_w=1.0, leak=float(x[0]), qv0=float(x[1]) if tau else 0.0)
        return float(rn * rn), k, p, q
    return fit_budget


_LATEST = {}


def _no_time_reference():
    """The gas budget referred to the latest entry's own pumping time, vent and wall temperature."""
    orig_fe = D.front_end

    def front_end(cid, data, certs, fix, vac):
        cfg, obs, s_now, rng = orig_fe(cid, data, certs, fix, vac)
        ents = [o for o in obs if o["kind"] == "entry"]
        _LATEST["o"] = max(ents, key=lambda o: o["date"]) if ents else None
        return cfg, obs, s_now, rng

    def at_reference(cfg, params):
        o = _LATEST.get("o")
        if o is None:
            return orig_ar(cfg, params)
        qw = params["c_w"] * D.q_wall_nominal(cfg["surfaces"], o["t_h"], o["vent"], o["t_k"])
        mat, cm = D._seal_for(cfg, D.AUDIT, params["seal"])
        qp = D.q_perm(mat, cm, o["t_k"])
        qv = params["qv0"] * math.exp(-o["t_h"] / params["tau"]) if params["qv0"] and params["tau"] else 0.0
        parts = {"wall-outgassing": qw, "permeation": qp, "air-leak": params["leak"], "virtual-leak": qv}
        return parts, sum(parts.values())
    orig_ar = D.at_reference
    return front_end, at_reference


def _void_before_change():
    orig = D.front_end

    def front_end(cid, data, certs, fix, vac):
        cfg, obs, s_now, rng = orig(cid, data, certs, fix, vac)
        work = [r["date"] for r in data["maint"] if r["chamber"] == cid and r["date"] <= D.AUDIT]
        if work:
            last = max(work)
            kept = [o for o in obs if o["kind"] != "entry" or o["date"] >= last]
            obs = kept if any(o["kind"] == "entry" for o in kept) else obs
        return cfg, obs, s_now, rng
    return front_end


def _drop_oldest():
    orig = D.front_end

    def front_end(cid, data, certs, fix, vac):
        cfg, obs, s_now, rng = orig(cid, data, certs, fix, vac)
        ents = sorted([o for o in obs if o["kind"] == "entry"], key=lambda o: o["date"])
        if len(ents) >= 4:
            drop = ents[0]
            obs = [o for o in obs if o is not drop]
        return cfg, obs, s_now, rng
    return front_end


def _patches(name):
    """[(attribute of diagnose, replacement)] for one route or variation."""
    if name == "register_surfaces":
        return [("chamber_config", _wrap_config(_register_surfaces))]
    if name == "register_port":
        return [("chamber_config", _wrap_config(_register_port))]
    if name == "register_seal":
        return [("chamber_config", _wrap_config(_register_seal))]
    if name == "all_entries":
        return [("chamber_config", _wrap_config(_all_entries))]
    if name == "trust_register_seal":
        return [("candidate_structures", _structures(lambda s: s["seal"] is None))]
    if name == "leak_only":
        return [("candidate_structures", _structures(lambda s: s["trapped_from"] is None))]
    if name == "trust_certificate":
        return [("certificate_error", lambda cid, cfg, data: (1.0, None))]
    if name == "undated_certificates":
        return [("cert_factor", _undated(D.cert_factor))]
    if name == "register_pump":
        return [("with_controller_pump", lambda cid, cfg, data: cfg)]
    if name == "latest_speed_test":
        return [("pump_changed_on", lambda cid, data: None)]
    if name == "commissioning_speed":
        return [("shop_speed_in", _commissioning_speed(D.shop_speed_in))]
    if name == "no_gas_correction":
        return [("gas_correction", lambda parts, seal: 1.0)]
    if name == "uncorrected_cathode":
        return [("correct_drift", lambda pts, cid, data: pts)]
    if name == "logged_serials":
        return [("crossed_serials", lambda data, certs: {})]
    if name == "ignore_vent_gas":
        return [("q_wall_nominal", _air_vent(D.q_wall_nominal))]
    if name == "ignore_load":
        return [("surfaces_with_load", lambda cfg, load: list(cfg["surfaces"]))]
    if name == "ignore_temperature":
        return [("theta", lambda e, t_k: 1.0)]
    if name == "table_outgassing":
        return [("fit_budget", _table_outgassing(D.fit_budget))]
    if name == "no_time_reference":
        fe, ar = _no_time_reference()
        return [("front_end", fe), ("at_reference", ar)]
    if name == "void_before_change":
        return [("front_end", _void_before_change())]
    if name == "skip_pump_gate":
        return [("PUMP_GATE", 0.0)]
    if name == "drop_oldest":
        return [("front_end", _drop_oldest())]
    if name == "mean_speed_test":
        return [("shop_speed_in", _mean_speed_test(D.shop_speed_in))]
    if name == "strict_seal":
        return [("OVERRIDE_CHI2", 2.0 * D.OVERRIDE_CHI2)]
    if name == "lenient_seal":
        return [("OVERRIDE_CHI2", 0.5 * D.OVERRIDE_CHI2)]
    if name == "equal_weights":
        return [("TEST_SD", {k: D.READ_SD for k in D.TEST_SD})]
    if name == "fine_tau_grid":
        return [("TAUS", [math.exp(i * math.log(D.TAU_MAX) / 95.0) for i in range(96)])]
    raise KeyError(name)


@contextlib.contextmanager
def patched(names):
    """Applies the named routes or variations to the reference for the length of the block, and restores it.
    Patches compose: each wraps whatever the attribute holds when it is applied."""
    saved = []
    flat = []
    for name in names:
        flat += FACE_VALUE if name == "face_value" else [name]
    try:
        for name in flat:
            # built only now, after the previous patch is in place, so that a wrapper wraps what the attribute
            # holds at this moment and not the original: built all at once, several wrappers of the same function
            # would each wrap the original and only the last would survive
            for attr, new in _patches(name):
                saved.append((attr, getattr(D, attr)))
                setattr(D, attr, new)
        yield
    finally:
        for attr, old in reversed(saved):
            setattr(D, attr, old)


NO_ANSWER = None


def run(data_dir, vac, name=None, o=None, only=None):
    """The reference audit with the named route or variations applied: {chamber: (cause, q_total, s_eff)}. With
    `only`, just those chambers are audited. A chamber the route leaves too little to fit (fewer observations than
    any budget has parameters) gets NO_ANSWER: whoever follows that route has no answer to write for it."""
    names = list(o or []) + ([name] if name else [])
    with patched(names):
        data = D.load_data(data_dir)
        certs = data["certs"]
        fix = D.crossed_serials(data, certs)
        out = {}
        for cid in sorted({r["chamber"] for r in data["register"]}):
            if only and cid not in only:
                continue
            try:
                r = D.audit_chamber(cid, data, certs, fix, vac)
            except D.Underdetermined:
                out[cid] = NO_ANSWER
                continue
            out[cid] = (r["cause"], r["q_total"], r["s_eff"])
    return out
