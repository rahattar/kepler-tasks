#!/usr/bin/env python3
"""Reference for the rod-pump core: python3 rodlift.py FIELD_DIR OUT_CSV
The rod string is linear, so it is carried in the frequency domain: a 2x2 transfer matrix a harmonic from the
polished rod to the pump. The pump is not linear, so it is solved in time, at the pump alone, against the
string's periodic compliance kernel. The tubing is taken from what the cards show, not from the register,
unless TRUST_REGISTER=1."""
import csv, json, os, sys
import numpy as np

G = 9.80665
MATERIAL = {"steel": (200e9, 8000.0), "fibreglass": (50e9, 2400.0)}
TUBING = {"60.3": 50.7, "73.0": 62.0, "88.9": 76.0}
E_TUBING = 200e9
TRUST = True   # the tubing as the well file has it
NT = int(os.environ.get("NT", "1024"))
THETA = float(os.environ.get("THETA", "1.0"))
NM = int(os.environ.get("NM", "32"))


def area(d_mm):
    return np.pi * (d_mm * 1e-3) ** 2 / 4


def transfer(sections, c, w):
    """T11, T12, T21, T22 of the string from top to bottom for angular frequencies w (any shape)."""
    w = np.asarray(w, float)
    ws = np.where(w == 0, 1e-9, w)
    T11 = np.ones(w.shape, complex); T12 = np.zeros(w.shape, complex)
    T21 = np.zeros(w.shape, complex); T22 = np.ones(w.shape, complex)
    for mat, d, L in sections:
        E, rho = MATERIAL[mat]; a = np.sqrt(E / rho); EA = E * area(d)
        g = np.sqrt(-ws * ws + 1j * c * ws + 0j) / a
        ch, sh = np.cosh(g * L), np.sinh(g * L)
        m11, m12, m21, m22 = ch, -sh / (EA * g), -EA * g * sh, ch
        T11, T12, T21, T22 = (m11 * T11 + m12 * T21, m11 * T12 + m12 * T22,
                              m21 * T11 + m22 * T21, m21 * T12 + m22 * T22)
    return T11, T12, T21, T22


def pump_step(sig, kap, Fo, Ap, pd, pi, h_av, s_low, s_high):
    r = pi / pd
    lg = np.maximum(0.0, (s_high - s_low) - h_av)
    s_tv = s_high - lg * (1 - r)
    s_Fo = sig - kap * Fo
    up = s_Fo >= s_high
    dn = (sig <= s_tv) & ~up
    mid = ~(up | dn)
    F = np.where(up, Fo, 0.0); s = np.where(up, s_Fo, sig)
    gas = mid & (lg > 1e-12)
    q = lg - s_high + sig
    b = kap * Ap * pd - q
    z = np.maximum(0.5 * (-b + np.sqrt(b * b + 4 * kap * Ap * pi * lg)), 1e-12)
    F = np.where(gas, np.clip(Ap * pd - Ap * pi * lg / z, 0.0, Fo), F)
    s = np.where(gas, s_high - lg + z, s)
    full = mid & ~gas
    F = np.where(full, np.clip((sig - s_high) / kap, 0.0, Fo), F)
    s = np.where(full, s_high, s)
    return F, s, np.where(dn, s, s_low), np.where(up | dn, s, s_high), dn


def modes(sections, nm=NM, ne=600):
    """Lowest modes of the string with its top held and its bottom free, mass-normalised: frequencies squared,
    value at the pump end, participation in a uniform acceleration, and the static remainders."""
    from scipy.linalg import eigh_tridiagonal, solve_banded
    tt = [L / np.sqrt(MATERIAL[m][0] / MATERIAL[m][1]) for m, d, L in sections]
    k_e, m_e = [], []
    for (mat, d, L), t in zip(sections, tt):
        E, rho = MATERIAL[mat]
        n = max(4, int(round(ne * t / sum(tt))))
        k_e += [E * area(d) * n / L] * n; m_e += [rho * area(d) * L / n] * n
    k_e = np.array(k_e); m_e = np.array(m_e); M = k_e.size
    m_n = np.zeros(M + 1); m_n[:-1] += m_e / 2; m_n[1:] += m_e / 2
    m = m_n[1:]                                             # the top node does not move of itself
    dg = k_e + np.append(k_e[1:], 0.0); off = -k_e[1:]
    lam, u = eigh_tridiagonal(dg / m, off / np.sqrt(m[:-1] * m[1:]), select="i", select_range=(0, nm - 1))
    phi = u / np.sqrt(m)[:, None]
    phiL = phi[-1]; gam = m @ phi
    ab = np.zeros((3, M)); ab[0, 1:] = off; ab[1] = dg; ab[2, :-1] = off
    c_stat = sum(L / (MATERIAL[mat][0] * area(d)) for mat, d, L in sections)
    d_stat = solve_banded((1, 1), ab, -m)[-1]
    return dict(w2=lam, phiL=phiL, gam=gam, c_res=c_stat - np.sum(phiL ** 2 / lam),
                d_res=d_stat + np.sum(gam * phiL / lam), m_tot=m_n.sum(), g_res=1.0 - np.sum(gam * phiL),
                m_res=m_n.sum() - np.sum(gam ** 2))


def forward(sec_of, md, c, Ap, pd, pi, comp_t, W, stroke, spm, lam, q_in, N=NT, theta=THETA):
    """Steady cycle at a batch of settings; every argument but c, N, theta is an array over the batch, md a dict
    of per-row modal arrays, sec_of a list (rows, sections) for the string's exact answer to the polished rod.
    Returns plunger stroke, liquid height, peak and minimum polished rod load."""
    R = stroke.size
    Fo = Ap * (pd - pi)
    T = 60.0 / spm; h = (T / N)[:, None]; w0 = 2 * np.pi / T
    # the part the polished rod drives with no load on the pump: exact, two harmonics
    th = 2 * np.pi * (np.arange(N) + 1) / N
    y_free = np.zeros((R, N)); f_free = np.zeros((R, N))
    for rows, sections in sec_of:
        for hn, amp in ((1, -0.5 * stroke[rows]), (2, -lam[rows] / 8 * stroke[rows])):
            T11, T12, T21, T22 = transfer(sections, c, hn * w0[rows])
            y_free[rows] += np.real((amp / T22)[:, None] * np.exp(1j * hn * th)[None, :])
            f_free[rows] += np.real((-T21 / T22 * amp)[:, None] * np.exp(1j * hn * th)[None, :])
        y_free[rows] += (stroke[rows] * (0.5 + lam[rows] / 8))[:, None]
    w2 = md["w2"]; phiL = md["phiL"]; gam = md["gam"]
    wd = np.sqrt(w2 - c * c / 4)
    lm = -c / 2 + 1j * wd
    E = np.exp(lm * h)
    Bg = -phiL * (E - 1) / lm
    pw = phiL / wd
    gw = gam * w2 / wd
    kap = theta * (-np.imag(np.sum(pw * Bg, axis=1))) + md["c_res"] + comp_t
    Bn = Bg * theta; Bo = Bg * (1 - theta)
    h_av = q_in / (Ap * spm / 60.0)
    z = np.zeros((R, w2.shape[1]), complex)
    s_low = Fo * comp_t; s_high = s_low.copy()
    S_p = np.zeros(R); pmax = np.zeros(R); pmin = np.zeros(R)
    was_dn = np.ones(R, bool); F = np.zeros(R)
    g_res = md["g_res"]; c_res = md["c_res"]
    for cyc in range(16):
        S_new = np.zeros(R); hi = np.full(R, -np.inf); lo = np.full(R, np.inf)
        for j in range(N):
            z = E * z
            z += Bo * F[:, None]
            base = y_free[:, j] + np.einsum("ij,ij->i", pw, z.imag)
            sig = base + Fo * comp_t
            sh0, sl0 = s_high, s_low
            F, s, s_low, s_high, dn = pump_step(sig, kap, Fo, Ap, pd, pi, h_av, s_low, s_high)
            opens = dn & ~was_dn
            S_new = np.where(opens, np.maximum(S_new, sh0 - sl0), S_new)
            was_dn = dn
            z += Bn * F[:, None]
            f0 = f_free[:, j] + F * g_res - np.einsum("ij,ij->i", gw, z.imag)
            hi = np.maximum(hi, f0); lo = np.minimum(lo, f0)
        ch = max(np.max(np.abs(S_new - S_p) / stroke), np.max(np.abs(hi - pmax) / (W + hi)), np.max(np.abs(lo - pmin) / (W + hi)))
        S_p, pmax, pmin = S_new, hi, lo
        if cyc > 1 and ch < 5e-4:                 # a few settings settle slowly; 16 cycles bring them within 0.2 per cent
            break
    forward.cycles = cyc + 1
    return S_p, np.minimum(h_av, S_p), W + pmax, W + pmin


def pump_card(sections, c, W, pos, load, spm, nh=40, up=8):
    """Position of the foot of the rods and the pump load through the cycle, from a surface card."""
    Nc = pos.size
    n = np.arange(Nc // 2 + 1)
    T11, T12, T21, T22 = transfer(sections, c, 2 * np.pi * spm / 60.0 * n)
    Ys = np.fft.rfft(pos); Fs = np.fft.rfft(load - W)
    keep = n <= nh
    Yp = np.where(keep, T11 * Ys + T12 * Fs, 0); Fp = np.where(keep, T21 * Ys + T22 * Fs, 0)
    M = up * Nc
    pad = np.zeros(M // 2 + 1, complex); pad[:Nc // 2] = Yp[:Nc // 2]; yp = np.fft.irfft(pad, M) * up
    pad = np.zeros(M // 2 + 1, complex); pad[:Nc // 2] = Fp[:Nc // 2]; fp = np.fft.irfft(pad, M) * up
    return yp, fp


def diagnose(sections, c, W, Ap, pd, cards, spm, comp_reg, comp_free):
    """Fluid load, tubing compliance and liquid supply of a well from its surface cards."""
    res = []
    for pos, load in cards:
        yp, fp = pump_card(sections, c, W, pos, load, spm)
        M = yp.size
        rel = (yp - yp.min()) / (yp.max() - yp.min())
        rising = np.gradient(yp) > 0
        hi = np.median(fp[rising & (rel > 0.45) & (rel < 0.85)])      # standing valve open, the full fluid load
        lo = np.median(fp[~rising & (rel > 0.05) & (rel < 0.25)])     # travelling valve open, no load
        Fo = hi - lo
        f = (fp - lo) / Fo
        # the pick-up of the load at the start of the upstroke: both valves shut on liquid
        i0 = int(np.argmin(yp))
        idx = (np.arange(M) + i0) % M
        fr, yr = f[idx], yp[idx]
        e = int(np.argmax(fr > 0.9))
        sel = (fr[:e] > 0.15) & (fr[:e] < 0.85)
        comp = np.polyfit(fr[:e][sel] * Fo, yr[:e][sel], 1)[0] if sel.sum() >= 4 else 0.0
        res.append((Fo, comp, f, yp))
    Fo = float(np.mean([r[0] for r in res])); comp_meas = float(np.mean([r[1] for r in res]))
    if TRUST:
        comp_t = comp_reg
    else:
        comp_t = comp_free if comp_meas > 0.5 * (comp_reg + comp_free) else comp_reg
    pi = pd - Fo / Ap
    r = pi / pd
    lgs, Ss = [], []
    for _, _, f, yp in res:
        s = yp + (1 - f) * Fo * comp_t
        M = s.size
        it = int(np.argmax(s)); s_high = s[it]; s_low = s.min(); S = s_high - s_low
        idx = (np.arange(M) + it) % M
        fd, sd = f[idx], s[idx]
        e = int(np.argmax(fd < 0.03)) or M // 2
        fd, sd = fd[:e], sd[:e]
        sel = (fd > 0.08) & (fd < 0.92)
        if sel.sum() < 3:
            lgs.append(0.0); Ss.append(S); continue
        fs_, ss_ = fd[sel], sd[sel]

        def miss(lg):
            z = np.maximum(lg - (s_high - ss_), 1e-9)
            return np.sum((np.clip((1 - r * lg / z) / (1 - r), 0, 1) - fs_) ** 2)
        grid = np.linspace(0.0, S, 400)
        k = int(np.argmin([miss(g) for g in grid]))
        fine = np.linspace(grid[max(k - 1, 0)], grid[min(k + 1, 399)], 200)
        lgs.append(float(fine[int(np.argmin([miss(g) for g in fine]))])); Ss.append(S)
    lg = float(np.mean(lgs)); S = float(np.mean(Ss))
    q_in = np.inf if lg < 0.03 * S else Ap * (S - lg) * spm / 60.0
    return Fo, pi, comp_t, comp_meas, q_in


def main(field_dir, out_csv):
    fld = json.load(open(os.path.join(field_dir, "field.json")))
    c = fld["damping_per_s"]; rho_f = fld["liquid_density_kg_m3"]
    rd = lambda name: list(csv.DictReader(open(os.path.join(field_dir, name))))
    wells = {w["well"]: w for w in rd("wells.csv")}
    rods = {}
    for r in rd("rods.csv"):
        rods.setdefault(r["well"], []).append((int(r["taper"]), r["material"], float(r["diameter_mm"]), float(r["length_m"])))
    cards = {}
    for r in rd("cards.csv"):
        cards.setdefault(r["well"], {}).setdefault(r["card"], []).append((int(r["sample"]), float(r["position_m"]), float(r["load_kN"])))
    sets = rd("settings.csv")
    per = {}
    for name, w in wells.items():
        sections = [(m, d, L) for _, m, d, L in sorted(rods[name])]
        L = float(w["pump_depth_m"]); Ap = area(float(w["plunger_mm"]))
        od = float(w["tubing_od_mm"]); At = np.pi * ((od * 1e-3) ** 2 - (TUBING["%.1f" % od] * 1e-3) ** 2) / 4
        pd = float(w["tubing_head_pressure_kPa"]) * 1e3 + rho_f * G * L
        W = sum(area(d) * Ls * G * (MATERIAL[m][1] - rho_f) for m, d, Ls in sections)
        comp_free = L / (E_TUBING * At)
        comp_reg = comp_free if w["anchor_depth_m"] == "" else (L - float(w["anchor_depth_m"])) / (E_TUBING * At)
        cs = []
        for cid, rows in cards[name].items():
            rows.sort()
            cs.append((np.array([p for _, p, _ in rows]), np.array([f for _, _, f in rows]) * 1e3))
        Fo, pi, comp_t, comp_meas, q_in = diagnose(sections, c, W, Ap, pd, cs, float(w["found_spm"]), comp_reg, comp_free)
        if os.environ.get("VERBOSE"):
            print(name, "Fo %.2f kN pi %.2f MPa comp reg %.3e free %.3e meas %.3e used %.3e q_in %.3e" %
                  (Fo / 1e3, pi / 1e6, comp_reg, comp_free, comp_meas, comp_t, q_in), file=sys.stderr)
        per[name] = dict(sec=sections, md=modes(sections), Ap=Ap, pd=pd, pi=pi, comp=comp_t, W=W, lam=float(w["unit_factor"]), q=q_in)
    wn = [r["well"] for r in sets]
    col = lambda k: np.array([per[x][k] for x in wn])
    md = {k: np.array([per[x]["md"][k] for x in wn]) for k in per[wn[0]]["md"]}
    st = np.array([float(r["surface_stroke_m"]) for r in sets]); sp = np.array([float(r["spm"]) for r in sets])
    Ap = col("Ap")
    wn_a = np.array(wn)
    sec_of = [(np.where(wn_a == x)[0], per[x]["sec"]) for x in per if (wn_a == x).any()]
    S_p, h_l, pmax, pmin = forward(sec_of, md, c, Ap, col("pd"), col("pi"), col("comp"), col("W"), st, sp, col("lam"), col("q"))
    liq = Ap * h_l * sp * 1440.0
    with open(out_csv, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["setting", "plunger_stroke_m", "liquid_m3_d", "pprl_kN", "mprl_kN"])
        for i, r in enumerate(sets):
            wr.writerow([r["setting"], "%.5f" % S_p[i], "%.4f" % liq[i], "%.4f" % (pmax[i] / 1e3), "%.4f" % (pmin[i] / 1e3)])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
