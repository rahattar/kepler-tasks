"""Reference: identify HZ-B from the records in /app/data and write the self-contained controller.

1. Camera offset: camera minus post-growth caliper over the eight bodies (the camera was zeroed on HZ-A).
2. Output-error fit over all eight bodies at once. Inputs are the logged heater power, pull rate and rotation
   setpoint. States are the superheat chain (dead time, two lags, gain kh0 (1 + 0.6 L/1500) on the power above
   p0(L)), the convection-lagged rotation, the meniscus height (exact one-minute discretisation) and the true diameter.
   Outputs are camera = D + offset - 1.2 (h - 6.8), caliper = D, and pyrometer = per-body offset + linear drift + S.
   The sheet physics (meniscus coefficient, growth angle, superheat sensitivity, v0(L), the forms of kh(L) and p0(L))
   is used as given. Per body: a growth offset and a trend in length, and the start diameter. Started from the HZ-A
   sheet values.
3. Writes controller.py: controller_template.py with the identified parameters, the diameter setpoint and the PS-R07
   table embedded (the controller runs alone and reads no file).
"""
import glob, json, os, sys
import numpy as np
from scipy.optimize import least_squares

DATA = os.environ.get("DATA", "/app/data")
OUT = os.environ.get("OUT", "/app/controller.py")
HERE = os.path.dirname(os.path.abspath(__file__))
D_SET = 302.0          # true-diameter setpoint: grind minimum 301.0 + the dip at the rotation steps + margin


def v_cool(L):
    return 0.98 - 0.10 * (1 - np.exp(-L / 400.0)) - 0.04 * (L / 1500.0)


def load(DATA):
    bodies = []
    for f in sorted(glob.glob(os.path.join(DATA, "logs", "*_minute.csv"))):
        a = np.genfromtxt(f, delimiter=",", names=True)
        c = np.genfromtxt(f.replace("_minute", "_caliper"), delimiter=",", names=True)
        bodies.append(dict(name=os.path.basename(f)[:5], t=a["time_min"], L=a["length_mm"], cam=a["camera_diameter_mm"],
                           vp=a["pull_rate_mm_min"], P=a["heater_power_kw"], T=a["pyrometer_c"], w=a["crucible_rpm_set"],
                           Lc=c["length_mm"], Dc=c["diameter_mm"]))
    return bodies


def camera_offset(bodies):
    offs = []
    for b in bodies:
        cam = np.interp(b["Lc"], b["L"], b["cam"])
        k = b["Lc"] > 50
        offs.append(np.mean(cam[k] - b["Dc"][k]))
    return float(np.mean(offs)), float(np.std(offs))



GH, PHI, CB, BETA = 0.30, 0.24, -1.2, 0.050
A1 = np.exp(-GH); C1 = (1 - A1) / GH; C3 = (1 - C1) / GH


def pad(bodies):
    n = max(len(b["t"]) for b in bodies)
    def P(k):
        out = np.zeros((n, len(bodies)))
        for j, b in enumerate(bodies):
            v = b[k]; out[:len(v), j] = v; out[len(v):, j] = v[-1]
        return out
    mask = np.zeros((n, len(bodies)), bool)
    for j, b in enumerate(bodies):
        mask[:len(b["t"]), j] = True
    return dict(t=P("t"), L=P("L"), cam=P("cam"), vp=P("vp"), P=P("P"), T=P("T"), w=P("w"), mask=mask, n=n)


def simulate(th, per, X, cam_off):
    dead, tau1, tau2, kh0, c_rot, tau_rot = th
    nb = X["P"].shape[1]
    a, g, D0 = per[:nb], per[nb:2 * nb], per[2 * nb:]
    n = X["n"]
    t, L, P, vp, w = X["t"], X["L"], X["P"], X["vp"], X["w"]
    # delayed power by interpolation (per body)
    Pd = np.empty_like(P)
    for j in range(nb):
        Pd[:, j] = np.interp(t[:, j] - dead, t[:, j], P[:, j], left=P[0, j])
    kh = kh0 * (1 + 0.6 * L / 1500.0)
    u = kh * (Pd - (100.0 - 14.0 * L / 1500.0))
    s1 = u[0].copy(); s = u[0].copy(); we = w[0].copy()
    x = np.zeros(nb); D = D0.copy()
    S_out = np.empty((n, nb)); x_out = np.empty((n, nb)); D_out = np.empty((n, nb))
    vc = v_cool(L)
    for i in range(n):
        S_out[i], x_out[i], D_out[i] = s, x, D
        vnat = vc[i] - c_rot * (we - 8.0) + a + g * L[i] / 1000.0 - BETA * s
        uu = vp[i] - vnat
        kd = 2.0 * vp[i] * PHI
        D = D - kd * (C1 * x + C3 * uu)
        x = A1 * x + C1 * uu
        s1 = s1 + (u[i] - s1) / tau1
        s = s + (s1 - s) / tau2
        we = we + (w[i] - we) / tau_rot
    return S_out, x_out, D_out


def residuals(z, X, bodies, cam_off, out=False):
    th, per = z[:6], z[6:]
    S, x, D = simulate(th, per, X, cam_off)
    res = []
    for j, b in enumerate(bodies):
        m = X["mask"][:, j] & (X["L"][:, j] > 30)
        cam_pred = D[m, j] + cam_off + CB * x[m, j]
        res.append((X["cam"][m, j] - cam_pred) / 0.15)
        Dc = np.interp(b["Lc"], X["L"][X["mask"][:, j], j], D[X["mask"][:, j], j])
        res.append((b["Dc"] - Dc) / 0.05)
        A = np.column_stack([np.ones(m.sum()), X["t"][m, j] / 1000.0])
        y = X["T"][m, j] - S[m, j]
        c = np.linalg.lstsq(A, y, rcond=None)[0]
        res.append((y - A @ c) / 0.3)
    if out:
        return S, x, D
    return np.concatenate(res)


def fit(bodies, th0, cam_off):
    X = pad(bodies)
    nb = len(bodies)
    z0 = np.concatenate([th0, np.zeros(nb), np.zeros(nb), np.array([b["Dc"][0] for b in bodies])])
    lb = np.concatenate([[5, 3, 2, 0.1, 0.0, 1.0], -0.2 * np.ones(nb), -0.2 * np.ones(nb), 290 * np.ones(nb)])
    ub = np.concatenate([[45, 90, 45, 1.0, 0.05, 30], 0.2 * np.ones(nb), 0.2 * np.ones(nb), 320 * np.ones(nb)])
    xs = np.concatenate([[3, 5, 3, 0.05, 0.003, 2], 0.01 * np.ones(nb), 0.01 * np.ones(nb), 0.3 * np.ones(nb)])
    r = least_squares(residuals, z0, args=(X, bodies, cam_off), bounds=(lb, ub), x_scale=xs, diff_step=1e-4, max_nfev=200)
    return r



def main():
    bodies = load(DATA)
    cam_off, cam_sd = camera_offset(bodies)
    r = fit(bodies, np.array([15.0, 25.0, 12.0, 0.45, 0.006, 5.0]), cam_off)
    dead, tau1, tau2, kh0, c_rot, tau_rot = (float(x) for x in r.x[:6])
    prm = dict(dead=dead, tau1=tau1, tau2=tau2, kh0=kh0, c_rot=c_rot, tau_rot=tau_rot, cam_off=cam_off, d_ref=D_SET)
    print("camera offset %.3f +- %.3f mm" % (cam_off, cam_sd))
    print("identified HZ-B:", {k: round(v, 4) for k, v in prm.items()})
    tab = open(os.path.join(DATA, "recipes", "perfect_si_r07.csv")).read().strip()
    src = open(os.path.join(HERE, "controller_template.py")).read()
    src = src.replace("PARAMS = None", "PARAMS = " + json.dumps(prm))
    src = src.replace('RECIPE_CSV = None', 'RECIPE_CSV = """' + tab + '\n"""')
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(src)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
