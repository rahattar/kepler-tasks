#!/usr/bin/env python3
"""Airflow at every survey point of a ventilation district package, to VS-4.

    python3 airflow.py PACKAGE_DIR OUT_CSV

Outline
  * Resistances (VS-4 s.3): airways from their latest pressure-quantity survey;
    an airway re-supported or enlarged on or after its latest survey on file
    is surveyed anew (one order to the survey crew, `pqsurvey`). Stoppings
    from the register, regulators from their table at the logged setting,
    doors closed/open, fan branches = ducting in series with the fan.
  * Settings (VS-4 s.5): every regulator/door stands at its latest log entry.
  * The non-fan part of the network is a two-terminal square-law network
    between ATM and the fan house, so for each set of settings it reduces to
    one equivalent resistance R_eq (p_ATM - p_FH = R_eq Q^2) and a fixed flow
    pattern scaled by the total flow Q.
  * Fans in parallel with stall-dip characteristics can have several steady
    operating points. Changes are slow against the air (s.5), so the fans
    follow their operating point quasi-statically through the log: R_eq is
    moved in small steps from each setting to the next (it is monotone in
    every branch resistance), the steady state being a local minimum of the
    network co-content; where an operating point vanishes the air settles
    along the descent path into the next steady state (fan stall/unstall).
"""
import sys, os, json, csv, math, subprocess, itertools, bisect
import numpy as np

# ----------------------------------------------------------------------------
# reading
# ----------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline='') as fh:
        rows = list(csv.reader(fh))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    head = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = [c.strip() for c in r] + [''] * (len(head) - len(r))
        out.append(dict(zip(head, r)))
    return out


def fnum(s, default=None):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def norm_time(s):
    s = s.strip().replace('T', ' ')
    return s


# ----------------------------------------------------------------------------
# square-law network (two terminals)
# ----------------------------------------------------------------------------

class TwoTerminalNet:
    """Branches between nodes, flow Q injected at src and taken out at dst."""

    def __init__(self, frm, to, nodes, src, dst):
        nb = len(frm)
        nn = len(nodes)
        A = np.zeros((nn, nb))
        A[frm, np.arange(nb)] -= 1.0
        A[to, np.arange(nb)] += 1.0
        b = np.zeros(nn)
        b[src] = -1.0
        b[dst] = 1.0
        keep = [i for i in range(nn) if i != src]
        Ar, br = A[keep], b[keep]
        U, s, Vt = np.linalg.svd(Ar)
        rank = int((s > 1e-9 * s[0]).sum())
        self.N = Vt[rank:].T.copy()          # cycle space basis
        self.qp = np.linalg.lstsq(Ar, br, rcond=None)[0]   # unit flow, particular
        self.nb = nb

    def solve(self, R, q0=None):
        """unit total flow; returns branch flows and R_eq = sum R|q|^3."""
        N, qp = self.N, self.qp
        if N.shape[1] == 0:
            q = qp.copy()
            return q, float((R * np.abs(q) ** 3).sum())
        x = np.zeros(N.shape[1]) if q0 is None else N.T @ (q0 - qp)

        def F(x):
            q = qp + N @ x
            return float((R * np.abs(q) ** 3).sum()) / 3.0, q

        f, q = F(x)
        for it in range(300):
            g = N.T @ (R * q * np.abs(q))
            w = 2.0 * R * np.maximum(np.abs(q), 1e-7)
            h = N.T @ (w[:, None] * N)
            try:
                dx = -np.linalg.solve(h, g)
            except np.linalg.LinAlgError:
                dx = -np.linalg.lstsq(h, g, rcond=None)[0]
            dec = -float(g @ dx)
            t = 1.0
            while True:
                fn, qn = F(x + t * dx)
                if fn <= f - 0.25 * t * dec or t < 1e-12:
                    break
                t *= 0.5
            x = x + t * dx
            f, q = fn, qn
            if dec <= 1e-15 * f:
                break
        # final polish of the cycle condition
        return q, float((R * np.abs(q) ** 3).sum())


# ----------------------------------------------------------------------------
# fans
# ----------------------------------------------------------------------------

class Fan:
    def __init__(self, qs, ps, Rd):
        order = np.argsort(qs, kind='stable')
        self.qs = np.asarray(qs, float)[order]
        self.ps = np.asarray(ps, float)[order]
        self.Rd = float(Rd)
        self.sl = np.diff(self.ps) / np.maximum(np.diff(self.qs), 1e-12)
        seg = (self.ps[:-1] + self.ps[1:]) / 2 * np.diff(self.qs)
        self.cum = np.concatenate([[0.0], np.cumsum(seg)])
        self.qmax = self.qs[-1]

    def _k(self, q):
        k = np.searchsorted(self.qs, q, side='right') - 1
        return min(max(int(k), 0), len(self.qs) - 2)

    def P(self, q):
        k = self._k(q)
        return self.ps[k] + self.sl[k] * (q - self.qs[k])

    def g(self, q):
        return self.P(q) - self.Rd * q * abs(q)

    def dg(self, q):
        return self.sl[self._k(q)] - 2.0 * self.Rd * abs(q)

    def G(self, q):            # integral of g from 0 to q
        k = self._k(q)
        if q <= self.qs[0]:
            k = 0
            intP = self.ps[0] * (q - self.qs[0]) + 0.5 * self.sl[0] * (q - self.qs[0]) ** 2
            base = 0.0
        else:
            base = self.cum[k]
            dq = q - self.qs[k]
            intP = self.ps[k] * dq + 0.5 * self.sl[k] * dq * dq
        return base + intP - self.Rd * q * q * abs(q) / 3.0

    # monotone pieces of g (for enumerating equilibria)
    def pieces(self):
        gq = np.array([self.g(q) for q in self.qs])
        pcs = []
        a = 0
        sg = np.sign(gq[1] - gq[0])
        for k in range(1, len(self.qs) - 1):
            s = np.sign(gq[k + 1] - gq[k])
            if s != sg and s != 0:
                pcs.append((a, k)); a = k; sg = s
        pcs.append((a, len(self.qs) - 1))
        return [(self.qs[a], self.qs[b]) for a, b in pcs]

    def inv(self, lo, hi, H):
        """q in [lo, hi] (a monotone piece of g, q >= 0) with g(q) = H."""
        ga, gb = self.g(lo), self.g(hi)
        if (H - ga) * (H - gb) > 0:
            return None
        k0 = self._k(lo + 1e-12)
        k1 = self._k(hi - 1e-12)
        for k in range(k0, k1 + 1):
            a, b = max(self.qs[k], lo), min(self.qs[k + 1], hi)
            fa, fb = self.g(a) - H, self.g(b) - H
            if fa == 0:
                return a
            if fa * fb > 0:
                continue
            # Rd q^2 - sl q + (H - ps_k + sl qs_k) = 0 on [a, b]
            A_, B_, C_ = self.Rd, -self.sl[k], H - self.ps[k] + self.sl[k] * self.qs[k]
            if A_ > 1e-15:
                disc = max(B_ * B_ - 4 * A_ * C_, 0.0)
                r = math.sqrt(disc)
                roots = [(-B_ - r) / (2 * A_), (-B_ + r) / (2 * A_)]
            elif B_ != 0:
                roots = [-C_ / B_]
            else:
                roots = []
            for x in roots:
                if a - 1e-9 <= x <= b + 1e-9:
                    return min(max(x, a), b)
            # numerical fallback
            for _ in range(100):
                m = 0.5 * (a + b)
                fm = self.g(m) - H
                if (fm > 0) == (fa > 0):
                    a, fa = m, fm
                else:
                    b = m
            return 0.5 * (a + b)
        return None


class FanSystem:
    """n fans in parallel against a network of equivalent resistance R."""

    def __init__(self, fans, metric=None):
        self.fans = fans
        self.n = len(fans)
        self.M = np.eye(self.n) if metric is None else metric
        self.Minv = np.linalg.inv(self.M)

    def grad(self, q, R):
        Q = q.sum()
        return np.array([R * Q * abs(Q) - f.g(qi) for f, qi in zip(self.fans, q)])

    def hess(self, q, R):
        Q = q.sum()
        return 2.0 * R * abs(Q) * np.ones((self.n, self.n)) - np.diag([f.dg(qi) for f, qi in zip(self.fans, q)])

    def energy(self, q, R):
        Q = q.sum()
        return R * Q * Q * abs(Q) / 3.0 - sum(f.G(qi) for f, qi in zip(self.fans, q))

    def is_pd(self, H):
        try:
            np.linalg.cholesky(H)
            return True
        except np.linalg.LinAlgError:
            return False

    def settle(self, q, R, maxit=20000):
        """steady state reached from q in the landscape of R: descend along
        the flow lines (small steps) where the energy is not locally convex,
        Newton where it is."""
        q = q.copy()
        E0 = self.energy(q, R)
        for it in range(maxit):
            g = self.grad(q, R)
            gn = np.abs(g).max()
            if gn < 1e-8:
                return q
            H = self.hess(q, R)
            if self.is_pd(H):
                d = -np.linalg.solve(H, g)
                dmax = np.abs(d).max()
                if dmax <= 1.0:
                    # Newton step, accepted while the energy does not rise
                    t = 1.0
                    ok = False
                    while t > 1e-4:
                        qn = q + t * d
                        En = self.energy(qn, R)
                        if En <= E0 + 1e-13 * abs(E0):
                            ok = True
                            break
                        t *= 0.5
                    if ok:
                        q, E0 = qn, En
                        if dmax * t < 1e-11:
                            return q
                        continue
            # descent along the flow lines, small steps
            d = -self.Minv @ g
            dmax = np.abs(d).max()
            if dmax == 0:
                return q
            step = 0.05
            while True:
                qn = np.maximum(q + d * (step / dmax), 0.0)
                En = self.energy(qn, R)
                if En < E0 or step < 1e-9:
                    break
                step *= 0.5
            if step < 1e-9:
                return q
            q, E0 = qn, En
        return q

    def track(self, q, R0, R1, ratio=1.004):
        """quasi-static change of R from R0 to R1."""
        if R1 == R0:
            return self.settle(q, R1)
        n = max(1, int(math.ceil(abs(math.log(R1 / R0)) / math.log(ratio))))
        for k in range(1, n + 1):
            Rk = R0 * (R1 / R0) ** (k / n)
            q = self.settle(q, Rk)
        return q

    def all_stable(self, R):
        """all stable steady states at R (by enumerating monotone pieces)."""
        pcs = [f.pieces() for f in self.fans]
        found = []
        for combo in itertools.product(*[range(len(p)) for p in pcs]):
            rng = []
            for f, p, c in zip(self.fans, pcs, combo):
                lo, hi = p[c]
                ga, gb = f.g(lo), f.g(hi)
                rng.append((min(ga, gb), max(ga, gb)))
            lo = max(r[0] for r in rng)
            hi = min(r[1] for r in rng)
            if not lo < hi:
                continue

            def F(H):
                s = 0.0
                for f, p, c in zip(self.fans, pcs, combo):
                    s += f.inv(p[c][0], p[c][1], H)
                return s - math.sqrt(max(H, 0.0) / R)

            Hs = np.linspace(lo, hi, 200)
            Fs = [F(H) for H in Hs]
            for k in range(len(Hs) - 1):
                if Fs[k] * Fs[k + 1] <= 0:
                    a, b, fa = Hs[k], Hs[k + 1], Fs[k]
                    for _ in range(80):
                        m = 0.5 * (a + b)
                        fm = F(m)
                        if (fm > 0) == (fa > 0):
                            a, fa = m, fm
                        else:
                            b = m
                    Hm = 0.5 * (a + b)
                    q = np.array([f.inv(p[c][0], p[c][1], Hm) for f, p, c in zip(self.fans, pcs, combo)])
                    q = self.settle(q, R)
                    if self.is_pd(self.hess(q, R)) and np.abs(self.grad(q, R)).max() < 1e-6:
                        if not any(np.abs(q - o).max() < 1e-3 for o in found):
                            found.append(q)
        return found


# ----------------------------------------------------------------------------
# main calculation
# ----------------------------------------------------------------------------

CHANGING_WORK = ('RESUPPORTED', 'ENLARGED')


def main(pkg, out_csv):
    branches = read_csv(os.path.join(pkg, 'branches.csv'))
    surveys = read_csv(os.path.join(pkg, 'surveys.csv'))
    work = read_csv(os.path.join(pkg, 'work_log.csv'))
    regs = read_csv(os.path.join(pkg, 'regulators.csv'))
    doors = read_csv(os.path.join(pkg, 'doors.csv'))
    fans_t = read_csv(os.path.join(pkg, 'fans.csv'))
    curves = read_csv(os.path.join(pkg, 'fan_curves.csv'))
    log = read_csv(os.path.join(pkg, 'log.csv'))
    points = read_csv(os.path.join(pkg, 'points.csv'))
    try:
        district = json.load(open(os.path.join(pkg, 'district.json')))
    except Exception:
        district = {}
    allowance = int(fnum(district.get('survey_allowance', 0), 0) or 0)

    names = [b['branch'] for b in branches]
    kind = {b['branch']: b['kind'].strip().lower() for b in branches}
    bidx = {n: i for i, n in enumerate(names)}

    # ---- airway resistances from surveys --------------------------------
    latest = {}          # branch -> (date, R)
    for s in surveys:
        b = s['branch']
        dp, q = fnum(s['dp_Pa']), fnum(s['q_m3_s'])
        if b not in bidx or dp is None or q is None or q == 0:
            continue
        R = dp / (q * abs(q))
        dt = s['date'].strip()
        if b not in latest or dt >= latest[b][0]:
            latest[b] = (dt, R)

    need = []            # (priority, work date, branch); 0 = surely changed since its survey
    airways = [n for n in names if kind[n] == 'airway']
    for b in airways:
        if b not in latest:
            need.append((0, '', b))
            continue
        sd = latest[b][0]
        best = None
        for w in work:
            if w['branch'] != b:
                continue
            wk = w['work'].strip().upper()
            if wk == 'INSPECTED':
                continue
            wd = w['date'].strip()
            if wd > sd:
                pr = 0 if wk in CHANGING_WORK else 1
            elif wd == sd:
                pr = 2      # same day: the survey may have come before the job
            else:
                continue
            if best is None or pr < best[0]:
                best = (pr, wd)
        if best is not None:
            need.append((best[0], best[1], b))
    need.sort(key=lambda t: (t[0], t[1]))
    order = [b for _, _, b in need][:allowance] if allowance > 0 else []

    fan_br = [n for n in names if kind[n] == 'fan']
    # spare allowance: read the fans as the district stands now, to check the
    # operating state the fans have been followed into
    spare = allowance - len(order)
    check_fans = list(fan_br[:max(spare, 0)])
    order = order + check_fans

    measured = {}
    if order:
        try:
            r = subprocess.run(['pqsurvey', pkg] + order, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3 and parts[0] in bidx:
                        dp, q = fnum(parts[1]), fnum(parts[2])
                        if dp is not None and q is not None:
                            measured[parts[0]] = (dp, q)
            else:
                sys.stderr.write('pqsurvey: ' + r.stdout + r.stderr + '\n')
        except Exception as e:
            sys.stderr.write('pqsurvey failed: %s\n' % e)

    R_air = {}
    known = [v[1] for v in latest.values() if v[1] > 0]
    R_fallback = float(np.median(known)) if known else 0.01
    for b in airways:
        if b in measured and b not in check_fans and measured[b][1] != 0:
            dp, q = measured[b]
            R_air[b] = dp / (q * abs(q))
        elif b in latest:
            R_air[b] = latest[b][1]
        else:
            R_air[b] = R_fallback
            sys.stderr.write('no resistance for airway %s\n' % b)

    # ---- regulators, doors -----------------------------------------------
    regtab = {}
    for r in regs:
        regtab.setdefault(r['regulator'], []).append((fnum(r['setting']), fnum(r['resistance_Ns2_m8'])))
    for k in regtab:
        regtab[k].sort()

    def reg_R(item, setting):
        tab = regtab[item]
        x = fnum(setting)
        for s, R in tab:
            if abs(s - x) < 1e-9:
                return R
        xs = np.array([t[0] for t in tab]); Rs = np.log(np.array([t[1] for t in tab]))
        return float(np.exp(np.interp(x, xs, Rs)))

    doortab = {d['door']: (fnum(d['resistance_closed_Ns2_m8']), fnum(d['resistance_open_Ns2_m8'])) for d in doors}

    def door_R(item, setting):
        s = setting.strip().lower()
        c, o = doortab[item]
        return o if s.startswith('open') else c

    # ---- states from the log ---------------------------------------------
    for r in log:
        r['time'] = norm_time(r['time'])
    log = sorted(log, key=lambda r: r['time'])      # stable: file order kept within a time
    cur = {}
    state_list = []
    t_open = log[0]['time']
    for r in log:
        if r['time'] == t_open:
            cur[r['item']] = r['setting']
            continue
        if not state_list:
            state_list.append((t_open, dict(cur)))
        cur[r['item']] = r['setting']
        state_list.append((r['time'], dict(cur)))   # changes one at a time
    if not state_list:
        state_list.append((t_open, dict(cur)))
    times = [t for t, _ in state_list]

    # network without the fan branches
    fan_rows = [b for b in branches if kind[b['branch']] == 'fan']
    fh_nodes = set(b['from_node'] for b in fan_rows)
    to_nodes = set(b['to_node'] for b in fan_rows)
    nonfan = [b for b in branches if kind[b['branch']] != 'fan']
    nodes = sorted(set(b['from_node'] for b in nonfan) | set(b['to_node'] for b in nonfan) | fh_nodes | to_nodes)
    nid = {n: i for i, n in enumerate(nodes)}
    FH = next(iter(fh_nodes))
    TOP = next(iter(to_nodes))
    if len(fh_nodes) != 1 or len(to_nodes) != 1:
        sys.stderr.write('warning: fans do not all join the same two nodes\n')
    net = TwoTerminalNet(np.array([nid[b['from_node']] for b in nonfan]),
                         np.array([nid[b['to_node']] for b in nonfan]), nodes, nid[TOP], nid[FH])

    def resistances(st):
        R = np.zeros(len(nonfan))
        for i, b in enumerate(nonfan):
            k = kind[b['branch']]
            if k == 'airway':
                R[i] = R_air[b['branch']]
            elif k == 'stopping':
                R[i] = fnum(b['resistance_Ns2_m8'], 0.0)
            elif k == 'regulator':
                R[i] = reg_R(b['item'], st[b['item']])
            elif k == 'door':
                R[i] = door_R(b['item'], st[b['item']])
            else:
                R[i] = fnum(b['resistance_Ns2_m8'], 0.0)
        return R

    unit = []
    Req = []
    cache = {}
    q0 = None
    for t, st in state_list:
        R = resistances(st)
        key = R.tobytes()
        if key in cache:
            u, re = cache[key]
        else:
            u, re = net.solve(R, q0)
            cache[key] = (u, re)
        q0 = u
        unit.append(u)
        Req.append(re)

    # ---- fans ------------------------------------------------------------
    fans = []
    ftab = {f['fan']: f for f in fans_t}
    fbybranch = {f['branch']: f for f in fans_t}
    for b in fan_rows:
        f = ftab.get(b['item']) or fbybranch.get(b['branch'])
        model, blade = f['model'], fnum(f['blade_setting'])
        pts = [(fnum(c['flow_m3_s']), fnum(c['pressure_Pa'])) for c in curves
               if c['model'] == model and abs(fnum(c['blade_setting'], -99) - blade) < 1e-9]
        if not pts:
            # blade setting between catalogue settings: interpolate the table
            sets = sorted(set(fnum(c['blade_setting']) for c in curves if c['model'] == model))
            lo = max(s for s in sets if s <= blade); hi = min(s for s in sets if s >= blade)
            A = [(fnum(c['flow_m3_s']), fnum(c['pressure_Pa'])) for c in curves if c['model'] == model and fnum(c['blade_setting']) == lo]
            B = [(fnum(c['flow_m3_s']), fnum(c['pressure_Pa'])) for c in curves if c['model'] == model and fnum(c['blade_setting']) == hi]
            w = (blade - lo) / (hi - lo)
            pts = [(a[0] * (1 - w) + bb[0] * w, a[1] * (1 - w) + bb[1] * w) for a, bb in zip(A, B)]
        fans.append(Fan([p[0] for p in pts], [p[1] for p in pts], fnum(b['resistance_Ns2_m8'], 0.0)))
    sysf = FanSystem(fans)

    def run_from(qinit):
        qs = [qinit]
        q = qinit
        for k in range(1, len(Req)):
            q = sysf.track(q, Req[k - 1], Req[k])
            qs.append(q)
        return qs

    cands = sysf.all_stable(Req[0])
    if not cands:
        q = np.array([f.qmax * 0.6 for f in fans])
        cands = [sysf.settle(q, Req[0])]
    cands.sort(key=lambda q: -q.sum())
    fan_q = run_from(cands[0])
    mpos = [i for i, b in enumerate(fan_rows) if b['branch'] in check_fans and b['branch'] in measured]
    if mpos:
        meas = np.array([measured[fan_rows[i]['branch']][1] for i in mpos])
        scale = max(abs(meas).max(), 1.0)

        def mismatch(fq):
            return float(np.abs(fq[-1][mpos] - meas).max())

        if mismatch(fan_q) > 0.03 * scale and len(cands) > 1:
            best = (mismatch(fan_q), fan_q)
            for c in cands[1:]:
                fq = run_from(c)
                if mismatch(fq) < best[0]:
                    best = (mismatch(fq), fq)
            fan_q = best[1]
        if mismatch(fan_q) > 0.03 * scale:
            sys.stderr.write('warning: fan state at the end of the log %s differs from survey %s\n'
                             % (fan_q[-1][mpos], meas))

    # ---- survey points ---------------------------------------------------
    fanpos = {b['branch']: i for i, b in enumerate(fan_rows)}
    nfpos = {b['branch']: i for i, b in enumerate(nonfan)}
    out = []
    for p in points:
        t = norm_time(p['time'])
        k = bisect.bisect_right(times, t) - 1
        if k < 0:
            k = 0
        b = p['branch']
        if b in fanpos:
            v = fan_q[k][fanpos[b]]
        elif b in nfpos:
            v = fan_q[k].sum() * unit[k][nfpos[b]]
        else:
            sys.stderr.write('point %s: no branch %s\n' % (p['point'], b))
            v = 0.0
        out.append((p['point'], float(v)))
    with open(out_csv, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['point', 'flow_m3_s'])
        for pt, v in out:
            w.writerow([pt, '%.6f' % v])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
