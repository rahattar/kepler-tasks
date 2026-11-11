#!/usr/bin/env python3
"""The design rules of flare-load-study, recomputed from the sealed definition and checked.

The rules are what the task was built to, not observations of it. Any change to isim.py that breaks one of them
makes this exit non-zero.

The second half measures what each layer of the study is worth: the sealed state is set back to what the records
would say if that layer were missed, the six rows are recomputed, and the worst change is compared with the
tolerance the verifier allows. A layer worth less than the tolerance is not a layer at all.

    python3 tune.py
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import isim as S  # noqa: E402

LOAD_SPREAD = 10.0       # the governing load must be this many times the smallest
LAYER_MARGIN = 1.0       # a layer must move some row by at least this many tolerances
IDENTIFY_MARGIN = 0.02   # an identified quantity differs from its data sheet by this much
MATCH_MARGIN = 0.01      # or else matches it within this much
FLOORED = 1              # exactly this many rows sit below the pressure floor
MARGIN = 0.08            # the re-rating must clear, and the bore below it miss, the limit by this much
FLARE_TIP_NOW = None     # filled from the sealed model below
RECORDED_SHUTOFF = 582.0  # the last performance test on record, made before the rotating element was renewed


def pump_head_needed():
    """The head P-401 would have to make to reach PSV-405's relieving pressure."""
    vid = "PSV-405"
    p1 = S.ITEMS[vid]["set_now"] * (1.0 + S.OVER_OTHER) + S.ATM
    rho = S.liq("bottoms_product", S.PUMP["temp_C"], "rho")
    return (p1 - (S.PUMP["suction_barg"] + S.ATM)) * 1.0e5 / (rho * 9.81)


def fresh():
    """A separate copy of the sealed model, so a layer can be reverted without disturbing this one."""
    spec = importlib.util.spec_from_file_location("isim_layer", os.path.join(HERE, "isim.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --------------------------------------------------------------------------- the layers
def revert_elevation(m):
    m.raised_now = lambda item: 0.0


def revert_tie_in(m):
    m.TIE_IN["PSV-407"] = m.TIE_IN_SHEET["PSV-407"]


def revert_settings(m):
    for it in m.ITEMS.values():
        it["set_now"] = it["set_reg"]


def revert_air_supply(m):
    m.DRIVEN["K-901"]["supply"] = "essential"


def move_safety_supply(m):
    m.DRIVEN["SIS"]["supply"] = "normal"


def revert_insulation(m):
    for v in ("V-403", "T-401"):
        m.VESSEL[v]["insul"]["fire_rated"] = False


def revert_meter(m):
    """The coefficient an agent recovers from the trend of the one meter that reads low, uncorrected."""
    bias = math.sqrt(m.RD_CONFIG / m.RD_NOW)
    for c in m.CV.values():
        if c["meter"] == m.METER_BIAS:
            c["actual"] *= bias


def revert_coefficients(m):
    for c in m.CV.values():
        c["actual"] = c["sheet"]


def revert_reboilers(m):
    m.reb_ua = lambda name: m.REB[name]["design_kw"] / (
        m.sat("steam", m.REB[name]["steam_barg"] + m.ATM, "t") - m.REB[name]["bot_normal_C"])


def revert_pump(m):
    m.PUMP["now_shutoff_m"] = m.PUMP["sheet_shutoff_m"]


def revert_coupling(m):
    """The study taken in sequence: rates at no built-up pressure, the header worked out once afterwards."""
    m.BELLOWS.update({v: True for v in m.IDS})      # a balanced device feels nothing, which is what a
                                                    # sequential reading amounts to for every device


def revert_tip(m):
    m.FLARE["tip_k"] = m.TIP_K_OLD          # the tip the 2019 study worked to, since replaced


def revert_pump_record(m):
    m.PUMP["now_shutoff_m"] = RECORDED_SHUTOFF   # the last test on record, before the element was renewed


LAYERS = [
    ("the column re-set 0.90 m higher since the data book", revert_elevation),
    ("the tie-in moved after the isometrics were issued", revert_tie_in),
    ("the two valves reset in situ since the register", revert_settings),
    ("the air compressor moved to the normal supply", revert_air_supply),
    ("the safety system left on the essential supply", move_safety_supply),
    ("the fire-resistant insulation fitted since the study", revert_insulation),
    ("the feed meter's stale configured density", revert_meter),
    ("the control valve coefficients the trend gives", revert_coefficients),
    ("the reboiler coefficient-area the record gives", revert_reboilers),
    ("the pump's shutoff head from its data sheet", revert_pump),
    ("the tip measured rather than taken from the 2019 study", revert_tip),
    ("the pump measured rather than taken from the record", revert_pump_record),
    ("the system brought together rather than taken in sequence", revert_coupling),
]


def rules():
    t = S.truth()
    out = []

    # 1 every contingency puts something on the header
    empty = [c for c, r in t.items() if not r["valves"]]
    out.append(("every contingency puts at least one device on the header", not empty,
                ", ".join(empty) or "none"))

    # 2 no two contingencies have the same device set, or a row would be redundant
    seen, same = {}, []
    for c, r in t.items():
        if r["valves"] in seen:
            same.append("%s and %s" % (seen[r["valves"]], c))
        seen[r["valves"]] = c
    out.append(("no two contingencies name the same devices", not same, "; ".join(same) or "none"))

    # 3 every device of the register discharges somewhere, bar the one section 7 screens out
    used = {v for r in t.values() for v in r["valves"]}
    idle = sorted(set(S.IDS) - used)
    out.append(("every device discharges somewhere bar the screened one",
                idle == ["PSV-405"], ", ".join(idle) or "none"))

    # 4 every cause the devices admit is reached somewhere, bar the one the screen removes
    causes = {cause for r in t.values() for _, cause in r["parts"].values()}
    want = {"fire", "cooling_failure", "control_valve_failure"}
    out.append(("fire, cooling failure and control valve failure all arise",
                want <= causes, ", ".join(sorted(causes))))

    # 5 the loads span a wide enough range that the rows are not interchangeable
    loads = sorted(r["load"] for r in t.values())
    spread = loads[-1] / loads[0] if loads[0] else 1.0e9
    out.append(("the governing load is at least %.0f times the smallest" % LOAD_SPREAD,
                spread >= LOAD_SPREAD, "%.0f times" % spread))

    # 6 the pressure floor is exercised, and every other row stands clear of it
    low = [c for c, r in t.items() if r["back"] < S.BACK_FLOOR]
    clear = min((r["back"] for r in t.values() if r["back"] >= S.BACK_FLOOR), default=0.0)
    out.append(("exactly %d row sits below the pressure floor" % FLOORED, len(low) == FLOORED,
                ", ".join(low) or "none"))
    out.append(("every other row stands clear of the floor", clear >= 10.0 * S.BACK_FLOOR,
                "lowest %.4f against a floor of %.4f" % (clear, S.BACK_FLOOR)))

    # 7 the governing case passes the pressure the 2019 study called the end of the margin
    governing = max(t.values(), key=lambda r: r["load"])
    out.append(("the governing contingency passes 1.0 barg at the header inlet",
                governing["back"] > 1.0, "%.4f barg" % governing["back"]))

    # 8 the booking decides something: what the records leave for the crew must be worth the orders
    gap = abs(FLARE_TIP_NOW / S.TIP_K_OLD - 1.0)
    out.append(("the tip now installed differs from the one the 2019 study worked to",
                gap > S.TOL, "%+.1f per cent against a band of %.1f" % (100.0 * (FLARE_TIP_NOW / S.TIP_K_OLD - 1.0),
                                                                        100.0 * S.TOL)))
    need = pump_head_needed()
    recorded = RECORDED_SHUTOFF
    out.append(("the pump's recorded shutoff and its present one fall either side of the screen",
                recorded > need > S.PUMP["now_shutoff_m"],
                "recorded %.1f m, needed %.1f m, now %.1f m" % (recorded, need, S.PUMP["now_shutoff_m"])))

    # 9 the sweeps have to close, and close quickly, or the answer is not well defined
    worst_sweeps, worst_ratio = 0, 0.0
    for c in S.CONTINGENCIES:
        parts, inlet, at, sweeps = S.converge(c)
        worst_sweeps = max(worst_sweeps, sweeps)
        S.BACK_FELT.clear()
        steps = []
        for _ in range(6):
            p = S.relieving_set(c)
            inl, a = S.header_profile(p)
            steps.append(inl)
            S.BACK_FELT.clear()
            S.BACK_FELT.update(a)
        S.BACK_FELT.clear()
        gaps = [abs(steps[i + 1] - steps[i]) for i in range(len(steps) - 1)]
        ratios = [gaps[i + 1] / gaps[i] for i in range(len(gaps) - 1) if gaps[i] > 1.0e-9]
        worst_ratio = max([worst_ratio] + ratios)
    out.append(("the sweeps close on one answer", worst_ratio < 0.5,
                "worst step ratio %.3f" % worst_ratio))
    out.append(("the sweeps close quickly", worst_sweeps <= 20, "worst %d sweeps" % worst_sweeps))

    # 10 taking the study in sequence has to cost more than the band on more than one part
    seq = fresh()
    revert_coupling(seq)
    seq._TRUTH = None
    got, base = seq.truth(), S.truth()
    missed = []
    for c in S.CONTINGENCIES:
        if got[c]["valves"] != base[c]["valves"]:
            missed.append(c)
            continue
        for key in ("load", "back"):
            if key == "back" and base[c]["back"] < S.BACK_FLOOR:
                continue
            if base[c][key] and abs(got[c][key] / base[c][key] - 1.0) > S.TOL:
                missed.append(c)
                break
    out.append(("a sequential reading misses at least two contingencies", len(missed) >= 2,
                ", ".join(missed) or "none"))

    # 11 the re-rating is decided with room either side of the limit
    want = S.sizing()
    smaller = [b for b in sorted(S.TIP_BORES) if b < want["bore_mm"]]
    rejected = S.worst_felt(smaller[-1])[0] if smaller else None
    out.append(("the chosen bore clears the limit with room",
                want["share"] <= S.BACK_LIMIT * (1.0 - MARGIN),
                "%.2f%% against a limit of %.2f%%" % (100.0 * want["share"], 100.0 * S.BACK_LIMIT)))
    out.append(("the next bore down misses the limit with room",
                rejected is not None and rejected >= S.BACK_LIMIT * (1.0 + MARGIN),
                "%.1f mm leaves %.2f%%" % (smaller[-1], 100.0 * rejected) if smaller else "no smaller bore"))
    out.append(("the device left binding carries no bellows", not S.BELLOWS.get(want["device"]),
                "%s under %s" % (want["device"], want["contingency"])))

    # 12 each identified quantity is either clearly different from its data sheet or clearly the same
    pairs = []
    for tag, c in sorted(S.CV.items()):
        pairs.append(("%s coefficient" % tag, c["actual"], c["sheet"]))
    pairs.append(("P-401 shutoff head", S.PUMP["now_shutoff_m"], S.PUMP["sheet_shutoff_m"]))
    for vid in sorted(S.ITEMS):
        pairs.append(("%s set pressure" % vid, S.ITEMS[vid]["set_now"], S.ITEMS[vid]["set_reg"]))
    muddy = []
    for name, got, sheet in pairs:
        rel = abs(got / sheet - 1.0)
        if MATCH_MARGIN < rel < IDENTIFY_MARGIN:
            muddy.append("%s %+.1f%%" % (name, 100.0 * (got / sheet - 1.0)))
    out.append(("every identified quantity differs by %.0f per cent or matches within %.0f"
                % (100.0 * IDENTIFY_MARGIN, 100.0 * MATCH_MARGIN), not muddy,
                "; ".join(muddy) or "none"))
    return out


def layer_worth():
    """What each layer is worth: the worst row change when the plant is read as if the layer were missed."""
    base = S.truth()
    rows = []
    for name, revert in LAYERS:
        m = fresh()
        revert(m)
        m._TRUTH = None
        got = m.truth()
        worst, where, kind = 0.0, "", ""
        for c in S.CONTINGENCIES:
            if got[c]["valves"] != base[c]["valves"]:
                worst, where, kind = 1.0e9, c, "devices"
                break
            for key, label in (("load", "load"), ("back", "pressure")):
                if key == "back" and base[c]["back"] < S.BACK_FLOOR:
                    continue
                rel = abs(got[c][key] / base[c][key] - 1.0) if base[c][key] else 0.0
                if rel > worst:
                    worst, where, kind = rel, c, label
        rows.append((name, worst, where, kind))
    return rows


def main():
    global FLARE_TIP_NOW
    FLARE_TIP_NOW = S.FLARE["tip_k"]
    out = rules()
    worth = layer_worth()
    width = max(len(n) for n, _, _ in out)
    bad = 0
    print("Design rules of flare-load-study, from the sealed definition.\n")
    for name, ok, detail in out:
        if not ok:
            bad += 1
        print("%s %-*s %s" % ("pass" if ok else "FAIL", width, name, detail))

    print("\nWhat each layer is worth, against a tolerance of %.1f per cent:\n" % (100.0 * S.TOL))
    print("| Layer | Worst row change | Where | What changes |")
    print("|---|---|---|---|")
    thin = []
    for name, rel, where, kind in worth:
        shown = "the device set" if rel >= 1.0e8 else "%.1f%%" % (100.0 * rel)
        print("| %s | %s | %s | %s |" % (name, shown, where or "-", kind or "-"))
        if rel < LAYER_MARGIN * S.TOL:
            thin.append(name)
    if thin:
        bad += 1
    print("\nlayers worth less than the tolerance: %s" % ("; ".join(thin) if thin else "none"))
    print("\n%d rules, %d FAILED" % (len(out) + 1, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
