"""Wrong side of the bound (at most 1 of the 8 hidden presses wrong): the reference program with one check or step
left out at a time, graded on the hidden packages.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

NO_SCALE = ("    if abs(k - 1.0) > 0.05:\n        ps, pp = ps / k, pp / k\n", "")
NO_FIT = ("    p0g = fit_precharge(u, t, ps, q_p, loaded)\n    doc = u[\"accumulator\"][\"precharge_bar\"]\n"
          "    if abs(p0g - doc) / doc < 0.05:\n        p0g = doc\n", "    p0g = u[\"accumulator\"][\"precharge_bar\"]\n")
VARIANTS = {
    "pressures taken as logged (no scale check against the power balance)": [NO_SCALE],
    "precharge taken from the unit record (no check against the charging)": [NO_FIT],
    "neither check (the procedure as written)": [NO_SCALE, NO_FIT],
    "motor speed taken as the rated speed (no slip)": [
        ('    n = mo["synchronous_speed_rpm"] - (mo["synchronous_speed_rpm"] - mo["rated_speed_rpm"]) * P_shaft / mo["rated_power_kw"]',
         '    n = mo["rated_speed_rpm"] + 0 * P_shaft')],
    "volumetric efficiency taken as 1": [
        ("    return np.where(loaded, q_th * ev, 0.0), np.where(loaded, q_th, 0.0), ehm, loaded",
         "    return np.where(loaded, q_th, 0.0), np.where(loaded, q_th, 0.0), ehm, loaded")],
    "gas law from the precharge state (isothermal mean state left out)": [
        ("    vg = V0 * (p0g + P_ATM) / p_m * (p_m / (ps + P_ATM)) ** (1 / N_POLY)",
         "    vg = V0 * ((p0g + P_ATM) / (ps + P_ATM)) ** (1 / N_POLY)")],
}


def main():
    base = open(C.SOLUTION).read()
    print("Hidden presses wrong (of 8); the bound is 1.\n")
    r = C.grade_text(base)
    print("%-72s %d" % ("reference (solution/hpu.py)", r["wrong"]))
    for name, edits in VARIANTS.items():
        text = base
        for old, new in edits:
            assert old in text, (name, old)
            text = text.replace(old, new)
        r = C.grade_text(text)
        print("%-72s %d  %s" % (name, r["wrong"], "; ".join(C.misses(r))), flush=True)


if __name__ == "__main__":
    main()
