"""Writes the agent's documents, and the sealed files for the laboratory and the verifier, from the sealed
definition hbsim.py.

    python3 authoring/provenance/gen.py ROOT

ROOT/data gets the records and documents the agent reads (installed at /app/data); ROOT/sealed gets hbsim.py and
seed.json. Every number in the documents is taken from hbsim.py: the register shows the hoists as they were before the
maintenance log's changes (hbsim.REGISTER), and the log records the changes.
"""
import csv
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hbsim as S  # noqa: E402

OUT = "data"


def w(path, text):
    p = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def wcsv(path, header, rows):
    p = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", newline="") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)


def lowering_speed(h, hid):
    """as the register shows it: contactor hoists lower above synchronous speed"""
    if h["ctrl"] == "vfd" and hid not in ("H04", "H08", "H12"):
        return h["v"]
    return h["v"] * (3000.0 - h["n"]) / h["n"]


def control_text(h):
    if h["ctrl"] == "twospeed":
        poles = {1 / 6: "4/24", 1 / 4: "4/16"}[min((1 / 6, 1 / 4), key=lambda x: abs(x - h["slow"]))]
        return ("contactor, two-speed pole-changing motor (%s pole); the controller changes down to the slow speed "
                "before every stop" % poles)
    return "contactor, single speed"


def main(root):
    global OUT
    OUT = os.path.join(root, "data")
    sealed = os.path.join(root, "sealed")
    os.makedirs(sealed, exist_ok=True)
    shutil.copy(os.path.join(HERE, "hbsim.py"), os.path.join(sealed, "hbsim.py"))
    with open(os.path.join(sealed, "seed.json"), "w") as f:
        json.dump(json.load(open(os.path.join(HERE, "seed.json"))), f)
    reg = []
    for hid, h0 in S.HOISTS.items():
        h = dict(h0)
        h.update(S.REGISTER.get(hid, {}))
        gear = "worm, single stage" if S.GEAR.get(hid) == "worm" else "helical, three stage"
        ctrl = "contactor, single speed" if hid in ("H04", "H08", "H12") else control_text(h)
        reg.append([hid, h["name"], h["bay"], "%.1f" % (h["load"] / 1000), "%d" % h["hook"], "%d" % h["falls"],
                    "%d" % round(h["D"] * 1000), "%.1f" % h["v"], "%.1f" % lowering_speed(h, hid), gear, "%.1f" % h["ratio"], "%.2f" % h["eta"],
                    "%d" % h["glim"], "%g" % h["P"], "%d" % h["n"], "%.3f" % h["Jm"], "%.4f" % h["Jg"], ctrl,
                    "%d" % h["Tamb"], "%d" % round(h["slim"] * 1000), "%.2f" % h["amax"]])
    wcsv("hoist_register.csv",
         ["hoist", "crane", "bay", "rated_load_t", "hook_block_kg", "falls", "drum_pitch_diameter_mm",
          "hoisting_speed_m_per_min", "lowering_speed_rated_load_m_per_min", "gearbox", "gearbox_ratio", "gearbox_efficiency", "gearbox_peak_input_torque_Nm",
          "motor_kW", "motor_rpm", "motor_rotor_inertia_kgm2", "gearbox_inertia_at_input_kgm2", "control",
          "bay_air_temperature_C", "emergency_stop_travel_limit_mm", "emergency_stop_deceleration_limit_m_per_s2"],
         reg)
    wcsv("brake_wiring.csv", ["hoist", "brake_coil_supply", "brake_switching"],
         [[hid, "400 V AC via bridge rectifier, 180 V DC coil",
           "AC side (rectifier input switched)" if h["sw"] == "AC" else "DC side (coil circuit switched)"]
          for hid, h in S.HOISTS.items()])
    survey = []
    hours = {"H01": 152, "H02": 171, "H03": 166, "H04": 158, "H05": 149, "H06": 120, "H07": 162, "H08": 168,
             "H09": 155, "H10": 170, "H11": 164, "H12": 142}
    for hid, h in S.HOISTS.items():
        n = int(round(h["stops"] * hours[hid] / 2))
        survey.append([hid, "2025-09-08", "2025-10-03", hours[hid], n, n, "%d" % round(100 * h["lf"])])
    wcsv("duty_survey.csv", ["hoist", "survey_from", "survey_to", "operating_hours", "brake_applications_hoisting",
                             "brake_applications_lowering", "mean_load_percent_of_rated"], survey)
    log = [
        ["2023-04-12", "H01", "Hoist limit switches adjusted; overload device tested at 110 % of rated load."],
        ["2023-06-20", "H07", "Wire rope replaced (same construction and diameter)."],
        ["2023-09-18", "H05", "Re-reeved from 4 falls to 2 falls for a faster cycle; drum and gearbox unchanged. "
                              "Rated load reduced to 10 t; new 2-fall hook block (300 kg)."],
        ["2023-11-06", "H12", "Contactor control replaced by a frequency inverter with closed-loop hoist control "
                              "(encoder on the motor). The inverter brings the hoist to standstill before it applies the brake."],
        ["2024-01-15", "H03", "Gearbox oil changed; input shaft seal replaced."],
        ["2024-02-26", "H04", "Contactor control replaced by a frequency inverter with closed-loop hoist control "
                              "(encoder on the motor). The inverter brings the hoist to standstill before it applies the brake. "
                              "Light-load fast lowering enabled: up to 150 % of rated speed for loads up to 50 % of rated load."],
        ["2024-05-02", "H09", "Hook and hook block inspected, no defects."],
        ["2024-06-17", "H08", "Contactor control replaced by a frequency inverter with closed-loop hoist control "
                              "(encoder on the motor). The inverter brings the hoist to standstill before it applies the brake. "
                              "Light-load fast lowering enabled: up to 160 % of rated speed for loads up to 40 % of rated load."],
        ["2024-09-09", "H10", "Brake linings replaced and bedded in (20 stops with rated load)."],
        ["2025-03-24", "H11", "Pendant control replaced by radio remote control; functions unchanged."],
        ["2025-06-30", "H02", "Motor bearings replaced at the non-drive end."],
    ]
    wcsv("maintenance_log.csv", ["date", "hoist", "entry"], log)
    cat = [[s, v[0], S.LINING[s], "%.4f" % v[1], v[2], "%.2f" % v[3], round(v[4] * 1000), round(v[5] * 1000)]
           for s, v in S.SIZES.items()]
    wcsv("brake_catalogue.csv", ["size", "rated_torque_Nm", "friction_lining", "rotor_inertia_kgm2", "heat_capacity_J_per_K",
                                 "heat_dissipation_W_per_K", "engagement_time_DC_switching_ms",
                                 "engagement_time_AC_switching_ms"], cat)
    w("docs/catalogue.md", CATALOGUE)
    w("docs/procedure.md", PROCEDURE)
    w("docs/laboratory.md", LABORATORY)


CATALOGUE = """# Spring-applied brake, series SB: catalogue notes

Electromagnetically released, spring-applied disc brake with one rotor and two organic friction linings, for mounting
on the non-drive end of the motor. Sizes, ratings, lining grade and thermal data are in `brake_catalogue.csv`.

- Rated torque: the braking torque of a bedded-in brake with its linings at 20 C at 100 % setting. The torque is set
  with the adjusting ring, from 50 to 100 % of rated torque to a whole percent, and is proportional to the setting.
- Rotor inertia: the inertia of the rotor and hub, which turn with the motor shaft.
- Engagement time: from switching off the coil supply until the brake develops its torque, for the rated torque
  (100 % setting). With switching on the DC side the coil current is interrupted directly. With switching on the AC
  side the coil current decays through the rectifier and the brake engages later. The brake does not act on the motor
  before the engagement time.
- Heat capacity: rotor, linings and armature plate together, which heat up with each stop.
- Heat dissipation: the heat flow from the brake to the surrounding air per kelvin of lining temperature above it.
- Lining temperature limit: 300 C.
"""

PROCEDURE = """# Plant standard MS-14: selection of hoist brakes

Every electric hoist has one spring-applied brake on the motor's non-drive end. The brake's size and torque setting
are selected for the hoist as it is now and for its working duty, and must meet every requirement below.

1. Holding. The braking torque is at least 1.6 times the static torque that the rated load and the hook block exert
   at the brake shaft, taken without credit for the gearbox's efficiency, with the linings at the highest temperature
   they reach in the hoist's working duty.
2. Emergency stop, travel. If the power is cut while the hoist is lowering, the hook comes to rest within the
   register's emergency-stop travel limit, measured from the moment the power is cut. This holds for every
   combination of load and speed the hoist is allowed to lower at, with the linings at the temperature they reach in
   the working duty.
3. Emergency stop, deceleration. In an emergency stop the load's deceleration does not exceed the register's limit,
   for any permitted load and direction of travel and at any lining temperature reached in service.
4. Lining temperature. The linings stay below the catalogue's temperature limit in the working duty and through an
   emergency stop from it.
5. Gearbox. The braking torque does not exceed the gearbox's peak input torque at any lining temperature reached in
   service.

The working duty of each hoist is the one recorded in the duty survey of September and October 2025 (brake
applications per operating hour and the mean load). The brake's rotor turns with the motor and adds its inertia to
the motor's.
"""

LABORATORY = """# Brake laboratory

The laboratory runs two kinds of test.

    friction <T> [<lining>]               friction coefficient of a series SB organic lining
    engage <size> <setting> <AC|DC>       engagement time of a series SB brake on the test bench

`friction` measures a bedded-in specimen, cut from the lining batch the brakes are supplied from, against a disc held
at the temperature T you choose, from 20 to 320 C, and gives eight readings. The lining is O1 or O2, the grades in the
catalogue; without one the specimen is O1. `engage` fits springs for the setting you choose (a whole percent from 50
to 100) to a bench brake of that size, supplied as on the hoists, and times five engagements with switching on the
side you choose.

Run them from `/app`. Each test's readings are printed and saved under `/app/lab_reports`. The allowance for the whole
selection is 8 tests of either kind; the laboratory refuses further tests once it is used.
"""

if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else ".")
