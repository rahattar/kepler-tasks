"""Runs a submitted cooler selection program on the hidden case packages and rates each selected design at that
cooler's sealed design case.

Each hidden case package (hidden/<case>/) is copied to a scratch directory and the program is run there as the
unprivileged user nobody, with no environment, as `python3 -I design.py <case> <out.json>`, with a time limit. The
sealed design cases (hidden/truth.json) stay in this directory, which only root can read. A case is right when the
program writes a catalogue design that, rated by the plant rating standard (rate.py) at the sealed design case,
meets every limit of the case (oil outlet temperature within TOL_T, pressure drops within TOL_P, the tube velocity
range, the tube support span) at an installed price no more than TOL_C times the cheapest design that does. The
submission is accepted when at most MAX_WRONG cases are wrong.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog  # noqa: E402
import rate     # noqa: E402

MAX_WRONG = 1            # of 8 hidden cases, from the requirement (at least seven right)
TOL_T = 0.3              # K on the oil outlet limit: rating round-off between sound implementations of RS-12
TOL_P = 0.03             # relative, on the pressure drop limits, for the same reason
TOL_C = 1.06             # price, from the requirement (no more than 6 % above the cheapest compliant design)
TIME_LIMIT_S = 300
NOBODY = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--inh-caps=-all"]
KEYS = ("shell_id_mm", "tube", "tube_length_m", "tube_passes", "layout_deg", "baffle_cut_pct", "baffle_spacing_mm",
        "shells_in_series")


def run_one(program, case_dir, as_nobody=True):
    work = tempfile.mkdtemp(prefix="cooler_")
    os.chmod(work, 0o755)
    try:
        shutil.copy(program, os.path.join(work, "design.py"))
        shutil.copytree(case_dir, os.path.join(work, "case"))
        outdir = os.path.join(work, "out")
        os.makedirs(outdir)
        for top, dirs, files in os.walk(work):
            for n in dirs:
                os.chmod(os.path.join(top, n), 0o755)
            for n in files:
                os.chmod(os.path.join(top, n), 0o644)
        os.chmod(outdir, 0o777)
        out = os.path.join(outdir, "design.json")
        cmd = [sys.executable, "-I", os.path.join(work, "design.py"), os.path.join(work, "case"), out]
        if as_nobody:
            cmd = NOBODY + cmd
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": work, "OMP_NUM_THREADS": "2"}
        p = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=TIME_LIMIT_S)
        if p.returncode != 0:
            return None, "exit status %d: %s" % (p.returncode, p.stderr.strip()[-300:])
        with open(out) as f:
            return json.load(f), None
    except subprocess.TimeoutExpired:
        return None, "time limit of %d s exceeded" % TIME_LIMIT_S
    except Exception as e:                           # missing or malformed output
        return None, repr(e)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def judge(sel, truth):
    basis, case, pmin = truth["basis"], truth["case"], truth["min_price"]
    try:
        d = {k: sel[k] for k in KEYS}
        od, wall = catalog.TUBES[str(d["tube"])]
        s = int(d["shell_id_mm"])
        L = float(d["tube_length_m"])
        npass, lay, cut, ns = int(d["tube_passes"]), int(d["layout_deg"]), int(d["baffle_cut_pct"]), int(d["shells_in_series"])
        sp = float(d["baffle_spacing_mm"])
    except (KeyError, TypeError, ValueError) as e:
        return False, "not a design: %r" % e
    if not (s in catalog.SHELLS_MM and L in catalog.LENGTHS_M and npass in catalog.PASSES and lay in catalog.LAYOUTS
            and cut in catalog.CUTS and ns in (1, 2, 3) and sp == int(sp)
            and max(0.2 * s, 50.0) <= sp <= min(s, catalog.SPAN_MAX_MM[od] / 2)):
        return False, "not a catalogue design (or tube span over the TEMA limit)"
    nt = catalog.tube_count(s, od, lay, npass)
    dd = dict(shell_id_mm=s, tube_od_mm=od, tube_wall_mm=wall, tube_length_m=L, tube_passes=npass, layout_deg=lay,
              pitch_mm=1.25 * od, baffle_cut_pct=cut, baffle_spacing_mm=sp, shells_in_series=ns, tubes=nt)
    try:
        r = rate.rate(dd, basis)
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        return False, "design cannot be rated: %r" % e
    price = catalog.price(s, L, nt, od, npass, lay) * ns
    ok = (r["oil_out_c"] <= case["oil_outlet_max_c"] + TOL_T and r["dp_shell_kpa"] <= case["oil_dp_max_kpa"] * (1 + TOL_P)
          and r["dp_tube_kpa"] <= case["cw_dp_max_kpa"] * (1 + TOL_P)
          and case["cw_velocity_m_s"][0] <= r["tube_velocity"] <= case["cw_velocity_m_s"][1]
          and math.isfinite(r["oil_out_c"]) and price <= TOL_C * pmin)
    return ok, dict(price_ratio=round(price / pmin, 4), oil_out_c=round(r["oil_out_c"], 2),
                    dp_oil_kpa=round(r["dp_shell_kpa"], 1), dp_cw_kpa=round(r["dp_tube_kpa"], 1),
                    tube_velocity_m_s=round(r["tube_velocity"], 2))


def score(program, hidden=os.path.join(HERE, "hidden"), as_nobody=True):
    truth = json.load(open(os.path.join(hidden, "truth.json")))
    cases, wrong = {}, 0
    for name in sorted(truth):
        sel, err = run_one(program, os.path.join(hidden, name), as_nobody)
        if err:
            cases[name] = {"right": False, "error": err}
        else:
            ok, info = judge(sel, truth[name])
            cases[name] = {"right": ok, "design": sel, "rating": info}
        wrong += not cases[name]["right"]
    return {"accepted": wrong <= MAX_WRONG, "wrong": wrong, "cases": cases}


if __name__ == "__main__":
    r = score(sys.argv[1], as_nobody=os.geteuid() == 0)
    for k, v in r["cases"].items():
        print(k, "ok " if v["right"] else "BAD", v.get("error") or v["rating"])
    print("%d of %d wrong: %s" % (r["wrong"], len(r["cases"]), "accepted" if r["accepted"] else "rejected"))
