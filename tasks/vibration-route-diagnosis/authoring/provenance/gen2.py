"""Route packages from sealed machine cases.

    python3 gen2.py OUT_ROOT

OUT_ROOT/data/docs/                 condition_codes.md, route_package.md
OUT_ROOT/data/examples/u2-2026-10-20/  the example route with the analyst's report (diagnosis_report.csv)
OUT_ROOT/hidden/<route>/           six hidden routes; OUT_ROOT/hidden/truth.json
"""
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim2  # noqa: E402

MOTOR_BRG = ["6312/6310", "6313/6310", "6311/6309", "6314/6312"]
PUMP_BRG = ["6309/6309", "6310/6310", "6311/6311"]
FAN_BRG = ["22213/22213", "22216/22216", "22218/22218"]
CMP_BRG = ["NU310/7310", "NU311/7311"]
VTP_BRG = ["7311/6311", "7310/6310"]
STALE = {"6309": "NU309", "6310": "NU310", "6311": "NU311", "6312": "NU312", "22216": "22218", "22213": "22216",
         "6313": "6314"}


def speed(rng, poles, vfd=None):
    sync = 120.0 * (vfd or 60.0) / poles
    slip = rng.uniform(0.003, 0.012) if poles == 2 else rng.uniform(0.004, 0.017)
    return round(sync * (1 - slip), 1)


def make(rng, mid, kind, fault, comp, **flags):
    m = dict(id=mid, kind=kind, fault=fault, component=comp, severity=float(rng.uniform(0.9, 1.3)))
    if kind == "EP":
        m["poles"] = flags.pop("poles", int(rng.choice([2, 4])))
        m["vanes"] = int(rng.integers(5, 8))
        m["motor_brg"] = str(rng.choice(MOTOR_BRG))
        m["driven_brg"] = str(rng.choice(PUMP_BRG))
        m["points"] = ["MOT", "PMP"]
        m["tach"] = True
    elif kind == "CTF":
        m["poles"] = 4
        m["pinion_teeth"] = int(rng.integers(13, 20))
        m["gear_teeth"] = int(rng.integers(50, 81))
        m["blades"] = int(rng.integers(4, 9))
        m["motor_brg"] = str(rng.choice(MOTOR_BRG))
        m["driven_brg"] = ""
        m["points"] = ["MOT", "GBX"]
        m["tach"] = False
    elif kind == "BF":
        m["poles"] = 4
        m["blades"] = int(rng.integers(8, 15))
        m["motor_sheave_mm"] = int(rng.integers(16, 26)) * 10
        m["fan_sheave_mm"] = int(rng.integers(26, 46)) * 10
        m["belt_length_mm"] = int(rng.integers(18, 33)) * 100
        m["motor_brg"] = str(rng.choice(MOTOR_BRG))
        m["driven_brg"] = str(rng.choice(FAN_BRG))
        m["points"] = ["MOT", "FAN"]
        m["tach"] = False
    elif kind == "SC":
        m["poles"] = 4
        m["lobes"] = int(rng.choice([4, 5]))
        m["motor_brg"] = str(rng.choice(MOTOR_BRG))
        m["driven_brg"] = str(rng.choice(CMP_BRG))
        m["points"] = ["MOT", "CMP"]
        m["tach"] = True
    elif kind == "VTP":
        m["poles"] = 4
        m["vanes"] = int(rng.integers(4, 7))
        m["motor_brg"] = str(rng.choice(VTP_BRG))
        m["driven_brg"] = ""
        m["points"] = ["MOT"]
        m["tach"] = True
    if flags.pop("vfd", False):
        m["vfd_hz"] = round(float(rng.uniform(38, 56)), 1)
    m["rpm"] = speed(rng, m["poles"], m.get("vfd_hz"))
    m["nameplate_rpm"] = int(round(120 * 60.0 / m["poles"] * (0.985 if m["poles"] == 4 else 0.99) / 5) * 5)
    # the bearing that carries the defect, as fitted
    if fault.startswith("BEARING_"):
        reg = (m["motor_brg"] if comp == "motor" else m["driven_brg"]).split("/")[0]
        stale = flags.pop("stale", False)
        m["bearing_actual"] = STALE.get(reg, reg) if stale else reg
        if stale:
            m["stale"] = True
        m["bearing_resonance"] = float(rng.uniform(2600, 4200))
    if kind == "VTP":
        f1 = m["rpm"] / 60
        if fault == "RESONANCE":
            m["fn_x"] = round(f1 * float(rng.uniform(0.98, 1.04)), 2)
            m["fn_y"] = round(m["fn_x"] * float(rng.uniform(1.25, 1.45)), 2)
        else:
            # no natural frequency of either direction within 25 % of 1x or 2x
            while True:
                fx = f1 * float(rng.choice([rng.uniform(1.35, 1.6), rng.uniform(0.45, 0.65)]))
                fy = fx * float(rng.uniform(1.25, 1.45))
                if all(abs(f / (k * f1) - 1) > 0.25 for f in (fx, fy) for k in (1, 2)):
                    break
            m["fn_x"], m["fn_y"] = round(fx, 2), round(fy, 2)
    if kind == "EP":
        m["npsh_cav"] = fault == "CAVITATION"
    m.update(flags)
    return m


def cases(rng):
    """Sixty hidden machine cases (six routes of ten), with the data problems the example route does not show."""
    C = []
    add = lambda *a, **k: C.append(make(rng, None, *a, **k))  # noqa: E731
    # bearing defects
    add("EP", "BEARING_OUTER", "pump", high_fs_true=20480.0)
    add("EP", "BEARING_OUTER", "motor", crossed=True)
    add("BF", "BEARING_OUTER", "fan", high_fs_true=12800.0)
    add("SC", "BEARING_OUTER", "compressor", bad_sensor="MOT")
    add("EP", "BEARING_OUTER", "pump", stale=True)
    add("EP", "BEARING_INNER", "pump", high_fs_true=20480.0)
    add("EP", "BEARING_INNER", "pump", crossed=True)
    add("SC", "BEARING_INNER", "motor", tach_marks=2)
    add("EP", "BEARING_INNER", "pump", stale=True)
    add("CTF", "BEARING_INNER", "motor")
    add("EP", "BEARING_BALL", "pump", high_fs_true=20480.0)
    add("BF", "BEARING_BALL", "fan", stale=True)
    add("EP", "BEARING_BALL", "motor")
    add("EP", "BEARING_CAGE", "pump", stale=True)
    add("BF", "BEARING_CAGE", "fan")
    # gears
    add("CTF", "GEAR_TOOTH", "gear", high_fs_true=20480.0)
    add("CTF", "GEAR_TOOTH", "pinion")
    add("CTF", "GEAR_TOOTH", "gear")
    add("CTF", "GEAR_TOOTH", "pinion")
    # electrical
    add("EP", "ELECTRICAL", "motor", poles=2, tach_marks=2)
    add("EP", "ELECTRICAL", "motor", poles=2)
    add("SC", "ELECTRICAL", "motor")
    add("BF", "ELECTRICAL", "motor", vfd=True)
    add("EP", "ROTOR_BAR", "motor", tach_marks=2)
    add("SC", "ROTOR_BAR", "motor", tach_marks=2)
    add("EP", "ROTOR_BAR", "motor")
    # mechanical
    add("EP", "MISALIGNMENT", "coupling", poles=2)
    add("EP", "MISALIGNMENT", "coupling", bad_sensor="PMP")
    add("SC", "MISALIGNMENT", "coupling")
    add("CTF", "MISALIGNMENT", "coupling")
    add("EP", "UNBALANCE", "pump", crossed=True)
    add("BF", "UNBALANCE", "fan", vfd=True)
    add("EP", "UNBALANCE", "pump", bad_sensor="MOT")
    add("VTP", "UNBALANCE", "motor")
    add("EP", "LOOSENESS", "pump", crossed=True)
    add("BF", "LOOSENESS", "motor", crossed=True)
    add("CTF", "LOOSENESS", "motor")
    add("EP", "LOOSENESS", "motor")
    add("SC", "LOOSENESS", "compressor")
    add("BF", "BELT", "belt", vfd=True)
    add("BF", "BELT", "belt", vfd=True)
    add("BF", "BELT", "belt")
    add("BF", "BELT", "belt", vfd=True)
    add("VTP", "RESONANCE", "structure")
    add("VTP", "RESONANCE", "structure")
    add("EP", "CAVITATION", "pump")
    add("EP", "CAVITATION", "pump", poles=2)
    add("EP", "CAVITATION", "pump")
    # healthy machines
    add("EP", "NONE", "none", bad_sensor="PMP")
    add("CTF", "NONE", "none", bad_sensor="MOT")
    add("EP", "NONE", "none", high_fs_true=20480.0)
    add("VTP", "NONE", "none")
    add("BF", "NONE", "none", vfd=True)
    add("SC", "NONE", "none")
    # sympathetic pairs: a healthy pump beside an unbalanced one on the same skid
    pairs = []
    for marks in (2, 1, 1):
        a = make(rng, None, "EP", "NONE", "none", poles=4, tach_marks=marks)
        b = make(rng, None, "EP", "UNBALANCE", "pump", poles=4)
        a["vanes"], a["driven_brg"], a["motor_brg"] = b["vanes"], b["driven_brg"], b["motor_brg"]
        a["rpm"] = round(b["rpm"] - float(rng.choice([-1, 1])) * float(rng.uniform(8, 12)), 1)
        a["neighbour_rpm"] = b["rpm"]
        pairs.append((a, b))
    return C, pairs


def routes(seed=2026):
    rng = np.random.default_rng(seed)
    C, pairs = cases(rng)
    order = rng.permutation(len(C))
    C = [C[i] for i in order]
    names = ["a1-2026-09-14", "a3-2026-09-22", "b2-2026-10-05", "c1-2026-10-08", "c4-2026-10-13", "d2-2026-10-27"]
    out = {nm: [] for nm in names}
    for i, (a, b) in enumerate(pairs):
        out[names[2 * i]] += [a, b]
    it = iter(C)
    for nm in names:
        while len(out[nm]) < 10:
            out[nm].append(next(it))
    rest = list(it)
    assert not rest, len(rest)
    for nm in names:
        prefix = nm[0].upper()
        for j, m in enumerate(out[nm]):
            tag = {"EP": "P", "CTF": "CT", "BF": "F", "SC": "AC", "VTP": "VP"}[m["kind"]]
            m["id"] = "%s%s-%d%02d" % (tag, prefix, int(nm[1]), j + 1)
        for a, b in pairs:
            if a in out[nm]:
                a["skid"] = b["skid"] = "skid %s-%s" % (nm[:2], a["id"][-2:])
                a["neighbour"] = b["id"]
    return out


EXAMPLE = [
    dict(id="CWP-1", kind="EP", poles=2, rpm=3590.0, vanes=6, motor_brg="6313/6310", driven_brg="6309/6309",
         fault="ELECTRICAL", component="motor"),
    dict(id="CWP-2", kind="EP", poles=2, rpm=3588.0, vanes=6, motor_brg="6313/6310", driven_brg="6309/6309",
         fault="MISALIGNMENT", component="coupling"),
    dict(id="CWP-3", kind="EP", poles=2, rpm=3591.0, vanes=6, motor_brg="6313/6310", driven_brg="6309/6309",
         fault="BEARING_OUTER", component="pump", bearing_actual="6309"),
    dict(id="CTF-4", kind="CTF", poles=4, rpm=1779.0, pinion_teeth=17, gear_teeth=71, blades=6, motor_brg="6312/6310",
         driven_brg="", fault="GEAR_TOOTH", component="gear"),
    dict(id="CTF-5", kind="CTF", poles=4, rpm=1782.0, pinion_teeth=17, gear_teeth=71, blades=6, motor_brg="6312/6310",
         driven_brg="", fault="LOOSENESS", component="motor"),
    dict(id="SF-6", kind="BF", poles=4, rpm=1440.0, vfd_hz=49.0, blades=12, motor_sheave_mm=224, fan_sheave_mm=355,
         belt_length_mm=2300, motor_brg="6310/6309", driven_brg="22216/22216", fault="BELT", component="belt"),
    dict(id="AC-7", kind="SC", poles=4, rpm=1781.0, lobes=4, motor_brg="6313/6310", driven_brg="NU310/7310",
         fault="ROTOR_BAR", component="motor"),
    dict(id="HWP-8", kind="EP", poles=4, rpm=1774.0, vanes=7, motor_brg="6312/6310", driven_brg="6311/6311",
         fault="BEARING_INNER", component="pump", bearing_actual="NU311", stale=True),
    dict(id="HWP-9", kind="EP", poles=4, rpm=1768.0, vanes=7, motor_brg="6312/6310", driven_brg="6311/6311",
         fault="NONE", component="none", neighbour="HWP-10", neighbour_rpm=1780.0, skid="skid B"),
    dict(id="HWP-10", kind="EP", poles=4, rpm=1780.0, vanes=7, motor_brg="6312/6310", driven_brg="6311/6311",
         fault="UNBALANCE", component="pump", skid="skid B"),
    dict(id="VTP-11", kind="VTP", poles=4, rpm=1785.0, vanes=5, motor_brg="7311/6311", driven_brg="",
         fault="RESONANCE", component="structure", fn_x=30.2, fn_y=41.6),
    dict(id="BP-12", kind="EP", poles=2, rpm=3555.0, vanes=5, motor_brg="6312/6310", driven_brg="6309/6309",
         fault="CAVITATION", component="pump", npsh_cav=True),
]


def example_machines():
    out = []
    for m in EXAMPLE:
        m = dict(m)
        m.setdefault("severity", 1.0)
        m.setdefault("points", {"EP": ["MOT", "PMP"], "CTF": ["MOT", "GBX"], "BF": ["MOT", "FAN"],
                                "SC": ["MOT", "CMP"], "VTP": ["MOT"]}[m["kind"]])
        m.setdefault("tach", m["kind"] in ("EP", "SC", "VTP"))
        m.setdefault("nameplate_rpm", {2: 3560, 4: 1775}[m["poles"]])
        m.setdefault("bearing_resonance", 3300.0)
        out.append(m)
    return out


def captures_of(m):
    return ["low_x", "low_y", "high_x"] if m["kind"] == "VTP" else ["low_r", "low_a", "high_r"]


def write_route(d, name, machines, seed, log_extra=()):
    os.makedirs(d, exist_ok=True)
    entries = []
    for i, m in enumerate(machines):
        data = {}
        for pi, p in enumerate(m["points"]):
            data[p] = {}
            for ki, kind in enumerate(captures_of(m)):
                x = sim2.capture(m, p, kind, seed + 1000 * i + 10 * pi + ki)
                scale = float(np.ceil(np.abs(x).max() / 32000 * 1e6) / 1e6)
                data[p][kind] = (np.round(x / scale).astype(np.int16), scale)
        for p in m["points"]:
            # the collector stores what the sensor measured; with crossed points the file planned for one point
            # holds the other point's data (and its scale)
            src = [q for q in m["points"] if q != p][0] if m.get("crossed") else p
            arrays = {k: v[0] for k, v in data[src].items()}
            for kind in captures_of(m):
                entries.append(dict(machine=m["id"], point=p, capture=kind,
                                    direction={"r": "radial horizontal", "a": "axial", "x": "radial x",
                                               "y": "radial y"}[kind[-1]],
                                    sample_rate_hz=sim2.LOW_FS if kind.startswith("low") else sim2.HIGH_FS,
                                    samples=len(arrays[kind]), g_per_count=data[src][kind][1],
                                    file="%s_%s.npz" % (m["id"].lower(), p.lower())))
            np.savez_compressed(os.path.join(d, "%s_%s.npz" % (m["id"].lower(), p.lower())), **arrays)
        if m["tach"]:
            t = sim2.tach(m, seed + 1000 * i + 500)
            with open(os.path.join(d, "%s_tach.csv" % m["id"].lower()), "w", newline="") as f:
                f.write("pulse_time_s\n" + "".join("%.6f\n" % v for v in t))
        if m["kind"] == "VTP":
            fr = np.round(np.arange(5.0, 100.01, 0.25), 2)
            rr = np.random.default_rng(seed + 1000 * i + 700)

            def frf(fn, z):
                r = fr / fn
                return 1 / np.sqrt((1 - r * r) ** 2 + (2 * z * r) ** 2)
            hx = frf(m["fn_x"], 0.025) * (1 + rr.normal(0, 0.03, len(fr)))
            hy = 0.8 * frf(m["fn_y"], 0.03) * (1 + rr.normal(0, 0.03, len(fr)))
            with open(os.path.join(d, "%s_impact_test.csv" % m["id"].lower()), "w", newline="") as f:
                f.write("frequency_hz,x_response_rel,y_response_rel\n")
                f.write("".join("%.2f,%.3f,%.3f\n" % v for v in zip(fr, hx, hy)))
    with open(os.path.join(d, "route.json"), "w") as f:
        json.dump(dict(route=name[:2].upper(), date=name[3:], captures=entries), f, indent=1)
    with open(os.path.join(d, "register.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["machine", "kind", "location", "motor_poles", "nameplate_rpm", "drive", "impeller_vanes",
                    "fan_blades", "compressor_lobes", "motor_bearings_de_nde", "driven_bearings_de_nde",
                    "gearbox_pinion_teeth", "gearbox_gear_teeth", "motor_sheave_mm", "fan_sheave_mm",
                    "belt_length_mm", "points", "tach"])
        kinds = {"EP": "end-suction pump", "CTF": "cooling tower fan", "BF": "belt-driven fan",
                 "SC": "screw compressor", "VTP": "vertical turbine pump"}
        for m in machines:
            drive = {"EP": "direct", "CTF": "right-angle gearbox", "BF": "V-belt", "SC": "direct",
                     "VTP": "direct"}[m["kind"]]
            if m.get("vfd_hz"):
                drive += ", VFD"
            w.writerow([m["id"], kinds[m["kind"]], m.get("skid", ""), m["poles"], m["nameplate_rpm"], drive,
                        m.get("vanes", "") if m["kind"] in ("EP", "VTP") else "", m.get("blades", ""),
                        m.get("lobes", ""), m["motor_brg"], m["driven_brg"], m.get("pinion_teeth", ""),
                        m.get("gear_teeth", ""), m.get("motor_sheave_mm", ""), m.get("fan_sheave_mm", ""),
                        m.get("belt_length_mm", ""), " ".join(m["points"]), "yes" if m["tach"] else "no"])
    with open(os.path.join(d, "bearing_data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["designation", "type", "rolling_elements", "element_diameter_mm", "pitch_diameter_mm",
                    "contact_angle_deg"])
        for k, (ty, n, dd, D, a) in sim2.BEARINGS.items():
            w.writerow([k, ty, n, dd, D, a])
    rng = np.random.default_rng(seed + 99)
    log = list(log_extra)
    for m in machines:
        if m.get("stale"):
            pos = "Motor DE" if m["component"] == "motor" else {"EP": "Pump", "BF": "Fan", "SC": "Compressor"}.get(
                m["kind"], "Driven") + " DE"
            when = np.datetime64(name[3:]) - np.timedelta64(int(rng.integers(3, 41)), "D")   # before the survey
            assert str(when) < name[3:]
            log.append((str(when), m["id"],
                        "%s bearing replaced. Stores issued %s. Register not updated." % (pos, m["bearing_actual"])))
    log.sort()
    with open(os.path.join(d, "maintenance_log.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "machine", "entry"])
        for r in log:
            w.writerow(r)
    with open(os.path.join(d, "process_snapshot.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["machine", "flow_m3_h", "bep_flow_m3_h", "npsh_available_m", "npsh_required_m"])
        for m in machines:
            if m["kind"] in ("EP", "VTP"):
                bep = float(rng.choice([120, 160, 250, 400, 640]))
                if m.get("npsh_cav"):
                    q, na, nr = bep * rng.uniform(0.3, 0.45), rng.uniform(2.5, 4.5), rng.uniform(5.0, 7.0)
                else:
                    q, na, nr = bep * rng.uniform(0.85, 1.05), rng.uniform(9, 26), rng.uniform(2.5, 6.0)
                w.writerow([m["id"], round(q), round(bep), round(na, 1), round(nr, 1)])


def main(root):
    ex = example_machines()
    import shutil
    os.makedirs(os.path.join(root, "data", "docs"), exist_ok=True)
    for nm in sorted(os.listdir(os.path.join(HERE, "docs"))):
        shutil.copy(os.path.join(HERE, "docs", nm), os.path.join(root, "data", "docs", nm))
    d = os.path.join(root, "data", "examples", "u2-2026-10-20")
    write_route(d, "u2-2026-10-20", ex, 4100, log_extra=[
        ("2026-02-10", "AC-7", "Annual service. Oil and separator element changed."),
        ("2026-03-11", "CTF-4", "Gearbox oil changed."),
        ("2026-04-22", "SF-6", "Belt set replaced (3 x B-section)."),
        ("2026-05-06", "BP-12", "Duty change MOC-118: flow reduced to the line 3 demand."),
        ("2026-06-18", "HWP-10", "Impeller replaced with the stores spare."),
        ("2026-09-30", "CWP-2", "Motor returned from rewind and reinstalled; coupling reassembled.")])
    with open(os.path.join(d, "diagnosis_report.csv"), "w") as f:
        f.write("machine,fault,component\n" + "".join("%s,%s,%s\n" % (m["id"], m["fault"], m["component"]) for m in ex))
    truth = {}
    for i, (nm, ms) in enumerate(routes().items()):
        write_route(os.path.join(root, "hidden", nm), nm, ms, 5000 + 1000 * 37 * i)
        truth[nm] = {m["id"]: [m["fault"], m["component"]] for m in ms}
    with open(os.path.join(root, "hidden", "truth.json"), "w") as f:
        json.dump(truth, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
