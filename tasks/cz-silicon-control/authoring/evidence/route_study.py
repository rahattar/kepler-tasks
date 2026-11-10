"""Routes against the gate on the eight graded bodies (in-process: the verifier's plant and score, no sandbox).
Each MPC route is the reference controller (solution/supervisor_template.py) with a different model; the fab loops
are the records' fast-pull loops run on PS-R07. Figures: worst 5 mm growth-rate error (% of program), lowest true
diameter and the mean true diameter (mm), 50-1500 mm. Gate: +-1 %, >= 301.0 mm, mean <= 303.0 mm.

    python3 route_study.py > route_study.txt      (about 40 min on one core)
"""
import io, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
import puller as PU
import supervisor_template as CT
import gen

CT.RECIPE_CSV = open(os.path.join(ROOT, "environment", "data", "recipes", "perfect_si_r07.csv")).read()
RC = PU.RECIPES["perfect_si"]
IDENT = dict(dead=25.735, tau1=32.149, tau2=10.213, kh0=0.3661, c_rot=0.0145, tau_rot=6.877, cam_off=0.797)   # fit.py
TRUE = {k: PU.HZ[k] for k in ("dead", "kh0", "tau1", "tau2", "c_rot", "tau_rot", "cam_off")}
SHEET = {k: PU.SHEET[k] for k in ("dead", "kh0", "tau1", "tau2", "c_rot", "tau_rot", "cam_off")}


class MPCRoute:
    def __init__(self, prm, d_ref=302.0, **kw):
        self.c = CT.MimoMPC(CT.Recipe(CT.RECIPE_CSV), dict(prm), d_ref=d_ref, **kw)

    def step(self, m):
        return self.c.step(m)


class Independent:
    """A controller written independently of the reference, from the records alone (authoring/evidence/independent/
    a and b): its own identification and structure, loaded from its directory with its own data files."""
    def __init__(self, sub):
        import importlib.util
        d = os.path.join(HERE, "independent", sub)
        spec = importlib.util.spec_from_file_location("independent_" + sub, os.path.join(d, "controller.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.c = mod.Controller()

    def step(self, m):
        return self.c.step(m)


def run(factory):
    res = []
    for seed in PU.GRADED_SEEDS:
        pl = PU.Puller(PU.make_body(seed, PU.HZ), RC)
        ctl = factory()
        while pl.L < PU.L_BODY and pl.t < 4000:
            m = pl.measure()
            m = dict(m, time_min=m["t"], pyrometer_c=1428.0 + m["pyrometer_k"])
            vp, p = ctl.step(m)
            pl.apply(vp, p, 1.0)
        res.append(PU.score(np.array(pl.log), l0=50.0, win=0.01, avg_mm=5))
    return res


def show(name, factory):
    r = run(factory)
    vg = max(x["vg_max"] for x in r); dmin = min(x["d_min"] for x in r); dm = float(np.mean([x["d_mean"] for x in r]))
    ok = vg <= 0.01 and dmin >= 301.0 and dm <= 303.0 and all(x["done"] for x in r)
    print("  %-66s V/G %.2f %%  D min %.2f  D mean %.2f  %s" % (name, 100 * vg, dmin, dm, "pass" if ok else "FAIL"),
          flush=True)


def main(part="all"):
    if part == "variations":
        return variations()
    if part == "independent":
        print("\ncontrollers written independently of the reference from the records (own identification and structure)")
        show("independent a: pull feedforward + heater MPC on diameter, KF (delay 28, lags 32/6 min)", lambda: Independent("a"))
        show("independent b: pull feedforward + heater MPC, KF with pyrometer and gain states", lambda: Independent("b"))
        return
    print("gate: growth rate within +-1 % (5 mm averages), true D >= 301.0 mm, mean true D <= 303.0 mm\n")
    show("reference: identified HZ-B (fit.py), setpoint 302.0", lambda: MPCRoute(IDENT))
    show("identified HZ-B, setpoint 301.8", lambda: MPCRoute(IDENT, d_ref=301.8))
    show("identified HZ-B, setpoint 302.4", lambda: MPCRoute(IDENT, d_ref=302.4))
    show("true HZ-B model, setpoint 302.0", lambda: MPCRoute(TRUE))
    print("\ncontrollers written independently of the reference from the records (own identification and structure)")
    show("independent a: pull feedforward + heater MPC on diameter, KF (delay 28, lags 32/6 min)", lambda: Independent("a"))
    show("independent b: pull feedforward + heater MPC, KF with pyrometer and gain states", lambda: Independent("b"))
    print("\nshortcuts")
    show("fab fast-pull loops on PS-R07 (pull rate on camera diameter 304)", lambda: gen.FabLoops(RC))
    show("design-sheet (HZ-A) model, camera taken at face value", lambda: MPCRoute(SHEET))
    show("design-sheet model, camera offset from the caliper", lambda: MPCRoute(dict(SHEET, cam_off=0.797)))
    show("design-sheet model, offset corrected, setpoint 304.5", lambda: MPCRoute(dict(SHEET, cam_off=0.797), d_ref=304.5))
    show("identified model, camera taken at face value", lambda: MPCRoute(dict(IDENT, cam_off=0.0)))
    show("identified model, rotation steps not previewed", lambda: MPCRoute(IDENT, preview=False))
    show("identified model but HZ-A rotation effect", lambda: MPCRoute(dict(IDENT, c_rot=SHEET["c_rot"])))
    show("identified model but HZ-A heater gain", lambda: MPCRoute(dict(IDENT, kh0=SHEET["kh0"])))
    show("identified model but HZ-A heater gain, setpoint 303.4", lambda: MPCRoute(dict(IDENT, kh0=SHEET["kh0"]), d_ref=303.4))
    if part == "all":
        variations()


def variations():
    print("\nsound variations of the identified model (identification spread over subsets of the logs: dead time\n"
          "23.2-25.7 min, kh0 0.361-0.371, rotation effect 0.0140-0.0149, convection lag 6.2-6.9 min)")
    for key, f in (("dead", 0.9), ("dead", 1.1), ("kh0", 0.95), ("kh0", 1.05), ("c_rot", 0.95), ("c_rot", 1.05),
                   ("tau1", 0.8), ("tau1", 1.2)):
        show("identified, %s x %.2f" % (key, f), lambda: MPCRoute(dict(IDENT, **{key: IDENT[key] * f})))
    print("\nlarger model errors need a higher setpoint, which the mean limit allows up to about 302.9 mm")
    for key, f in (("kh0", 1.1), ("c_rot", 0.9)):
        show("identified, %s x %.2f, setpoint 302.0" % (key, f), lambda: MPCRoute(dict(IDENT, **{key: IDENT[key] * f})))
        show("identified, %s x %.2f, setpoint 302.6" % (key, f),
             lambda: MPCRoute(dict(IDENT, **{key: IDENT[key] * f}), d_ref=302.6))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
