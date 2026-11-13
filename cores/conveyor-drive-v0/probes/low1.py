import sys, json, math
import numpy as np, pandas as pd

G = 9.80665
N0 = 1500.0
ORDER = {'head1': 0, 'head2': 1, 'tail': 2}


class Flight:
    pass


def load(d):
    meta = json.load(open(d + '/line.json'))
    fl = pd.read_csv(d + '/flights.csv')
    fl['flight'] = fl['flight'].astype(str)
    fl = fl.set_index('flight')
    pr = pd.read_csv(d + '/profile.csv'); pr['flight'] = pr['flight'].astype(str)
    dr = pd.read_csv(d + '/drives.csv'); dr['flight'] = dr['flight'].astype(str)
    dr['drive'] = dr['drive'].astype(str).str.strip()
    sv = pd.read_csv(d + '/surveys.csv'); sv['flight'] = sv['flight'].astype(str)
    sv['drive'] = sv['drive'].astype(str).str.strip()
    feed = pd.read_csv(d + '/feed.csv').sort_values('step')['feed_t_h'].to_numpy(float) / 3.6
    flights = []
    for name in meta['flights']:
        name = str(name)
        r = fl.loc[name]
        F = Flight(); F.name = name
        p = pr[pr.flight == name].sort_values('section')
        F.l = p.length_m.to_numpy(float); F.h = p.rise_m.to_numpy(float)
        F.L = F.l.sum(); F.H = F.h.sum()
        F.edges = np.concatenate([[0.0], np.cumsum(F.l)])
        F.slope = F.h / F.l
        F.mB = float(r.belt_kg_m); F.mc = float(r.idlers_carry_kg_m); F.mr = float(r.idlers_return_kg_m)
        F.C = float(r.secondary_factor); F.K = float(r.belt_stiffness_MN) * 1e6
        F.Tt = float(r.take_up_tension_kN) * 1e3
        ds = dr[dr.flight == name].copy()
        ds['o'] = ds.drive.map(ORDER); ds = ds.sort_values('o')
        F.drives = list(ds.drive)
        F.Pr = dict(zip(ds.drive, ds.rated_kW.astype(float) * 1e3))
        F.i = dict(zip(ds.drive, ds.gear_ratio.astype(float)))
        F.D = dict(zip(ds.drive, ds.pulley_diameter_mm.astype(float) / 1e3))
        F.e = dict(zip(ds.drive, ds.efficiency.astype(float)))
        F.sv = sv[sv.flight == name]
        F.f = 0.02
        flights.append(F)
    return meta, flights, feed


def v0(F, k):
    return math.pi * F.D[k] * N0 / (60.0 * F.i[k])


def tensions(F, Fd):
    """Fd: dict drive->force. returns dict drive->(T_on, T_off), T_load"""
    Rr = F.C * F.f * G * F.L * (F.mB + F.mr)
    Ttail_on = F.Tt + Rr - F.mB * G * F.H
    T = {}
    h2 = Fd.get('head2', 0.0)
    if 'head2' in Fd:
        T['head2'] = (F.Tt + h2, F.Tt)
    if 'head1' in Fd:
        T['head1'] = (F.Tt + h2 + Fd['head1'], F.Tt + h2)
    tl = Fd.get('tail', 0.0)
    if 'tail' in Fd:
        T['tail'] = (Ttail_on, Ttail_on - tl)
    return T, Ttail_on - tl


def calibrate(F):
    sv = F.sv
    camps = list(sv.groupby('campaign'))
    # rated slip: LS through origin of P on s
    F.sr = {}
    for k in F.drives:
        x = sv[sv.drive == k]
        s = 1 - x.input_rpm.to_numpy(float) / N0
        P = x.motor_kW.to_numpy(float) * 1e3
        F.sr[k] = F.Pr[k] * np.dot(s, s) / np.dot(s, P)
    w = F.L * (2 * F.mB + F.mc + F.mr)
    for it in range(30):
        Dn = {k: [] for k in F.drives}
        fs_num = 0.0; fs_den = 0.0
        for c, cs in camps:
            cs = cs.set_index('drive')
            q = float(cs.feed_t_h.iloc[0]) / 3.6
            vw = float(cs.belt_speed_m_s.iloc[0])
            Fd = {k: F.e[k] * float(cs.motor_kW[k]) * 1e3 / v0(F, k) for k in F.drives if k in cs.index}
            T, Tl = tensions(F, Fd)
            v = vw / (1 + Tl / F.K)
            for k in Fd:
                u = v * (1 + T[k][0] / F.K)
                n = float(cs.input_rpm[k])
                Dn[k].append(60 * F.i[k] * u / (math.pi * n))
            Fsum = sum(Fd.values())
            M = q * F.L / v
            rest = Fsum - G * q * F.H / v - q * v
            a = F.C * G * (w + M)
            fs_num += a * rest; fs_den += a * a
        newD = {k: float(np.mean(Dn[k])) for k in F.drives}
        F.D = newD
        F.f = fs_num / fs_den


def solve(F, Fres0, q, v_guess):
    """Fres0: resistance without q v term. returns v, forces"""
    ks = F.drives
    a = {k: F.e[k] * F.Pr[k] / (F.sr[k] * v0(F, k)) for k in ks}
    V0 = {k: v0(F, k) for k in ks}
    Rr = F.C * F.f * G * F.L * (F.mB + F.mr)
    Ttail = F.Tt + Rr - F.mB * G * F.H
    K = F.K; Tt = F.Tt

    def forces(v):
        Fd = {}
        h2 = 0.0
        if 'head2' in a:
            A = a['head2']; w0 = V0['head2']
            h2 = A * (1 - v * (1 + Tt / K) / w0) / (1 + A * v / (K * w0))
            Fd['head2'] = h2
        if 'head1' in a:
            A = a['head1']; w0 = V0['head1']
            Fd['head1'] = A * (1 - v * (1 + (Tt + h2) / K) / w0) / (1 + A * v / (K * w0))
        if 'tail' in a:
            A = a['tail']; w0 = V0['tail']
            Fd['tail'] = A * (1 - v * (1 + Ttail / K) / w0)
        return Fd

    def gfun(v):
        Fd = forces(v)
        return sum(Fd.values()) - Fres0 - q * v, Fd

    v = v_guess
    for _ in range(50):
        g0, Fd = gfun(v)
        dv = 1e-6
        g1, _ = gfun(v + dv)
        step = g0 / ((g1 - g0) / dv)
        v -= step
        if abs(step) < 1e-11:
            break
    g0, Fd = gfun(v)
    return v, Fd


def main():
    d, out = sys.argv[1], sys.argv[2]
    meta, flights, feed = load(d)
    dt = float(meta['step_s']); nI = int(meta['interval_steps'])
    for F in flights:
        calibrate(F)
    nS = len(feed)
    res = {}
    for F in flights:
        for k in F.drives:
            res[(F.name, k)] = (np.zeros(nS), np.zeros(nS))
    # load state per flight: lists of segment boundaries (positions, increasing from tail) and cumulative mass
    # represent as arrays pos (front edges of segments measured from tail) ; segments list of (length, mass)
    state = []
    for F in flights:
        state.append({'seg_len': [], 'seg_m': [], 'v': v0(F, F.drives[0]) * 0.99})
    for t in range(nS):
        q_in = feed[t]
        for fi, F in enumerate(flights):
            st = state[fi]
            # segments ordered from head (index 0) to tail (last); positions
            lens = np.array(st['seg_len']); ms = np.array(st['seg_m'])
            if len(lens):
                # tail-side position of each segment: segments stacked from tail
                rear = np.concatenate([[0.0], np.cumsum(lens[::-1])])  # from tail outward
                cm = np.concatenate([[0.0], np.cumsum(ms[::-1])])
                cum_at = np.interp(F.edges, rear, cm)
                Mj = np.diff(cum_at)
                M = cum_at[-1]
                # density at head
                # segment containing x=L from tail
                head_seg = None
            else:
                Mj = np.zeros(len(F.l)); M = 0.0
            Fres0 = F.C * F.f * G * (F.L * (2 * F.mB + F.mc + F.mr) + M) + G * float(np.dot(Mj, F.slope))
            v, Fd = solve(F, Fres0, q_in, st['v'])
            st['v'] = v
            T, Tl = tensions(F, Fd)
            for k in F.drives:
                P = Fd[k] * v0(F, k) / F.e[k]
                on, off = T[k]
                hi, lo = max(on, off), min(on, off)
                res[(F.name, k)][0][t] = P
                res[(F.name, k)][1][t] = hi / lo if lo > 0 else float('inf')
            # advance: add new segment at tail, move everything by v dt, remove beyond L
            st['seg_len'].append(v * dt); st['seg_m'].append(q_in * dt)
            # discharge: compute mass beyond L
            lens = st['seg_len']; ms = st['seg_m']
            total = sum(lens)
            # positions of head-end of oldest segment = total (all lengths from tail)
            out_m = 0.0
            excess = total - F.L
            while excess > 0 and lens:
                if lens[0] <= excess + 1e-12:
                    excess -= lens[0]; out_m += ms[0]
                    lens.pop(0); ms.pop(0)
                else:
                    frac = excess / lens[0]
                    out_m += ms[0] * frac
                    ms[0] *= (1 - frac); lens[0] -= excess
                    excess = 0
            q_in = out_m / dt
    rows = []
    for F in flights:
        for k in F.drives:
            P, tr = res[(F.name, k)]
            for j in range(0, (nS + nI - 1) // nI):
                a = P[j * nI:(j + 1) * nI] / 1e3; b = tr[j * nI:(j + 1) * nI]
                rows.append(('%s-%s-%03d' % (F.name, k, j + 1), a.mean(), a.max(), a.min(), b.max()))
    with open(out, 'w') as fo:
        fo.write('row,mean_kW,max_kW,min_kW,traction_peak\n')
        for r in rows:
            fo.write('%s,%.3f,%.3f,%.3f,%.5f\n' % r)


if __name__ == '__main__':
    main()
