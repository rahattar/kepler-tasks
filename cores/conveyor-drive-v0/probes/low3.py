import sys, os, json, math
import numpy as np, pandas as pd
from scipy.optimize import least_squares

G = 9.80665
N0 = 1500.0


class Flight:
    pass


def load(d):
    js = json.load(open(os.path.join(d, 'line.json')))
    fl = pd.read_csv(os.path.join(d, 'flights.csv')).set_index('flight')
    pr = pd.read_csv(os.path.join(d, 'profile.csv'))
    dr = pd.read_csv(os.path.join(d, 'drives.csv'))
    sv = pd.read_csv(os.path.join(d, 'surveys.csv'))
    feed = pd.read_csv(os.path.join(d, 'feed.csv')).sort_values('step')['feed_t_h'].to_numpy(float)
    flights = []
    for name in js['flights']:
        F = Flight()
        F.name = name
        r = fl.loc[name]
        F.mB = float(r.belt_kg_m); F.mc = float(r.idlers_carry_kg_m); F.mr = float(r.idlers_return_kg_m)
        F.C = float(r.secondary_factor); F.K = float(r.belt_stiffness_MN) * 1e6
        F.Tt = float(r.take_up_tension_kN) * 1e3
        p = pr[pr.flight == name].sort_values('section')
        F.l = p.length_m.to_numpy(float); F.h = p.rise_m.to_numpy(float)
        F.L = F.l.sum(); F.H = F.h.sum()
        F.edges = np.concatenate([[0.0], np.cumsum(F.l)])
        F.slope = F.h / F.l
        dd = dr[dr.flight == name]
        order = {'head1': 0, 'head2': 1, 'tail': 2}
        dd = dd.assign(o=dd.drive.map(order)).sort_values('o')
        F.drives = list(dd.drive)
        F.Pr = dd.rated_kW.to_numpy(float) * 1e3
        F.eff = dd.efficiency.to_numpy(float)
        F.v0nom = np.pi * dd.pulley_diameter_mm.to_numpy(float) / 1000 * N0 / (60 * dd.gear_ratio.to_numpy(float))
        F.sv = sv[sv.flight == name]
        flights.append(F)
    return js, flights, feed


def tensions(F, Fd, Rr):
    """return T_on, T_off per drive, T_load (tension at loading point)."""
    idx = {d: i for i, d in enumerate(F.drives)}
    n = len(F.drives)
    Ton = np.zeros(n); Toff = np.zeros(n)
    Ttail_on = F.Tt + Rr - F.mB * G * F.H
    Tload = Ttail_on
    if 'tail' in idx:
        i = idx['tail']
        Ton[i] = Ttail_on; Toff[i] = Ttail_on - Fd[i]; Tload = Toff[i]
    T = F.Tt
    if 'head2' in idx:
        i = idx['head2']; Toff[i] = T; T = T + Fd[i]; Ton[i] = T
    i = idx['head1']; Toff[i] = T; T = T + Fd[i]; Ton[i] = T
    return Ton, Toff, Tload


def calibrate(F):
    sv = F.sv
    camps = sorted(sv.campaign.unique())
    n = len(F.drives)
    S = np.zeros((len(camps), n)); P = np.zeros((len(camps), n))
    q = np.zeros(len(camps)); vw = np.zeros(len(camps))
    for c, cp in enumerate(camps):
        rows = sv[sv.campaign == cp].set_index('drive')
        q[c] = rows.feed_t_h.iloc[0] / 3.6
        vw[c] = rows.belt_speed_m_s.iloc[0]
        for i, d in enumerate(F.drives):
            S[c, i] = 1 - rows.loc[d, 'input_rpm'] / N0
            P[c, i] = rows.loc[d, 'motor_kW'] * 1e3
    # rated slip: P = Pr s / sr
    F.sr = F.Pr * (S * S).sum(0) / (S * P).sum(0)
    nc = len(camps)

    def res(x):
        v0 = x[:n]; f = x[n]; v = x[n + 1:]
        out = []
        Rr = F.C * f * G * F.L * (F.mB + F.mr)
        for c in range(nc):
            Fd = F.eff * P[c] / v0
            Ton, Toff, Tl = tensions(F, Fd, Rr)
            out.extend((v[c] * (1 + Ton / F.K) - v0 * (1 - S[c])) / (v0 * 1e-4))
            out.append((v[c] * (1 + Tl / F.K) - vw[c]) / (vw[c] * 5e-4))
            M = q[c] * F.L / v[c]
            Ftot = F.C * f * G * (F.L * (2 * F.mB + F.mc + F.mr) + M) + G * (q[c] * F.l / v[c] * F.slope).sum() + q[c] * v[c]
            out.append((Fd.sum() - Ftot) / (np.abs(Fd).sum() * 5e-3 + 1.0))
        return np.array(out)
    x0 = np.concatenate([F.v0nom, [0.02], vw])
    r = least_squares(res, x0, x_scale=np.concatenate([F.v0nom * 0.01, [0.005], vw * 0.01]))
    F.v0 = r.x[:n]; F.f = r.x[n]
    F.Rr = F.C * F.f * G * F.L * (F.mB + F.mr)
    F.A0 = F.C * F.f * G * F.L * (2 * F.mB + F.mc + F.mr)
    F.a = F.eff * F.Pr / (F.sr * F.v0)  # F_d = a (1 - u/v0)
    # linear structure: T_on = c0 + B @ Fd
    idx = {d: i for i, d in enumerate(F.drives)}
    B = np.zeros((n, n)); c0 = np.zeros(n)
    Ttail = F.Tt + F.Rr - F.mB * G * F.H
    if 'tail' in idx:
        c0[idx['tail']] = Ttail
    heads = [d for d in ('head2', 'head1') if d in idx]
    acc = []
    for d in heads:
        acc.append(idx[d]); i = idx[d]; c0[i] = F.Tt
        for j in acc:
            B[i, j] = 1.0
    F.B = B; F.c0 = c0


def solve_step(F, Mterm, q, vguess):
    # F_d = a (1 - v (1 + (c0 + B Fd)/K)/v0)
    n = len(F.drives)
    a, v0, K = F.a, F.v0, F.K
    I = np.eye(n)

    def fd(v):
        k = a * v / (v0 * K)
        A = I + k[:, None] * F.B
        b = a * (1 - v * (1 + F.c0 / K) / v0)
        return np.linalg.solve(A, b)

    def g(v):
        return fd(v).sum() - (Mterm + q * v)
    v1 = vguess; g1 = g(v1)
    v2 = v1 * (1 - 1e-4); g2 = g(v2)
    for _ in range(20):
        if g2 == g1:
            break
        v3 = v2 - g2 * (v2 - v1) / (g2 - g1)
        v1, g1 = v2, g2
        v2 = v3; g2 = g(v2)
        if abs(v2 - v1) < 1e-10:
            break
    return v2, fd(v2)


def main():
    d, out = sys.argv[1], sys.argv[2]
    js, flights, feed = load(d)
    dt = float(js['step_s']); ni = int(js['interval_steps'])
    for F in flights:
        calibrate(F)
    N = len(feed)
    nf = len(flights)
    Pall = [np.zeros((N, len(F.drives))) for F in flights]
    Trall = [np.zeros((N, len(F.drives))) for F in flights]
    # belt state: cumulative mass vs belt coordinate
    SIG = np.zeros((nf, N + 1)); CUM = np.zeros((nf, N + 1))
    Sb = np.zeros(nf); vb = [F.v0.mean() for F in flights]
    for k in range(N):
        qk = feed[k] / 3.6
        for fi, F in enumerate(flights):
            S = Sb[fi]
            sa = SIG[fi, :k + 1]; ca = CUM[fi, :k + 1]
            lo = max(0, np.searchsorted(sa, S - F.L - 1.0) - 1)
            sa = sa[lo:]; ca = ca[lo:]
            cm = np.interp(S - F.edges, sa, ca, left=ca[0], right=ca[-1])
            Mj = cm[:-1] - cm[1:]
            Mterm = F.A0 + F.C * F.f * G * Mj.sum() + G * (Mj * F.slope).sum()
            v, Fd = solve_step(F, Mterm, qk, vb[fi])
            vb[fi] = v
            Ton = F.c0 + F.B @ Fd
            Toff = Ton - Fd
            Pall[fi][k] = Fd * F.v0 / F.eff
            Trall[fi][k] = np.maximum(Ton, Toff) / np.minimum(Ton, Toff)
            Snew = S + v * dt
            SIG[fi, k + 1] = Snew; CUM[fi, k + 1] = CUM[fi, k] + qk * dt
            sa = SIG[fi, lo:k + 2]; ca = CUM[fi, lo:k + 2]
            dm = np.interp(Snew - F.L, sa, ca, left=ca[0]) - np.interp(S - F.L, sa, ca, left=ca[0])
            Sb[fi] = Snew
            qk = dm / dt
    rows = []
    nint = (N + ni - 1) // ni
    for fi, F in enumerate(flights):
        for di, dn in enumerate(F.drives):
            for j in range(nint):
                p = Pall[fi][j * ni:(j + 1) * ni, di] / 1e3
                t = Trall[fi][j * ni:(j + 1) * ni, di]
                rows.append(('%s-%s-%03d' % (F.name, dn, j + 1), p.mean(), p.max(), p.min(), t.max()))
    pd.DataFrame(rows, columns=['row', 'mean_kW', 'max_kW', 'min_kW', 'traction_peak']).to_csv(out, index=False, float_format='%.6f')


if __name__ == '__main__':
    main()
