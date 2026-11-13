#!/usr/bin/env python3
"""Airflow at every survey point of a ventilation district package, to VS-4.

usage: python3 airflow.py PACKAGE_DIR OUT_CSV

Method
------
* Resistances: airways from their latest pressure-quantity survey; airways re-supported or
  enlarged since their latest survey are surveyed again with the one `pqsurvey` order.
  Stoppings from the register, unless the survey campaigns (node balances of the surveyed
  airflows, all regulators and doors left as they stand during a campaign) show a stopping
  leaking far beyond what its built resistance allows; then its resistance comes from the
  campaign (and from the survey order when there is room in it).  Regulators and doors from
  their tables at the setting of their latest log entry.
* The district apart from the fans is a network of square-law branches, so for one set of
  settings it draws a total airflow Q through the fan house at suction s = R_eq Q^2, with the
  airflow in every branch proportional to Q.  R_eq and the branch airflows per unit Q are
  found once for every state of the log (loop-flow Newton on the network's content).
* The main fans stand in parallel: s = P_i(q_i) - R_duct,i q_i^2 for every fan i and
  Q = sum q_i.  Their catalogue characteristics have a stall dip, so for one R_eq several
  stable operating states can exist.  The flow follows the settings quasi-statically (a change
  takes a minute, the air follows in seconds), so the operating state is tracked through the
  log: it stays on its branch of stable equilibria while that exists and, where the branch
  ends (a fan passing its peak, or a stalled fan passing the bottom of its dip), the air
  settles where the transient (fan-branch inertia, gradient flow of the network content)
  carries it.
* Survey noise (each reading within 0.3 per cent) leaves R_eq uncertain by a fraction of a
  per cent; where a change brings a fan within that distance of a stall or recovery point,
  the possible histories are sampled and the one that agrees with the present state of the
  fans (read by a fan-branch survey in the order, when there is room for it) is taken.
"""
import sys, os, csv, json, math, subprocess, datetime
import numpy as np

DEBUG = bool(os.environ.get('AIRFLOW_DEBUG'))


def dbg(*a):
    if DEBUG:
        print(*a, file=sys.stderr)


# ----------------------------------------------------------------------------- reading
def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='') as f:
        rows = []
        for r in csv.DictReader(f):
            rows.append({(k or '').strip(): (v or '').strip() for k, v in r.items()})
        return rows


def fnum(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def pdate(s):
    s = s.strip()[:10]
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return datetime.date(1900, 1, 1)


# ----------------------------------------------------------------------------- network
class Network:
    """Passive square-law network carrying a unit flow from node src to node snk."""

    def __init__(self, names, frm, to, src, snk):
        self.names = list(names)
        nodes = sorted(set(frm) | set(to) | {src, snk})
        self.nodes = nodes
        idx = {n: i for i, n in enumerate(nodes)}
        self.idx = idx
        nb = len(names); nn = len(nodes)
        fr = np.array([idx[x] for x in frm], int); tt = np.array([idx[x] for x in to], int)
        adj = [[] for _ in range(nn)]
        for k in range(nb):
            adj[fr[k]].append((k, tt[k], 1.0)); adj[tt[k]].append((k, fr[k], -1.0))
        s = idx[src]; t = idx[snk]
        parent = [None] * nn; seen = [False] * nn; seen[s] = True; order = [s]; intree = np.zeros(nb, bool)
        i = 0
        while i < len(order):
            u = order[i]; i += 1
            for k, v, sg in adj[u]:
                if not seen[v]:
                    seen[v] = True; parent[v] = (u, k, sg); intree[k] = True; order.append(v)
        if not seen[t]:
            raise RuntimeError('fan house not connected to the surface through the district')
        self.reach = np.array(seen)

        def path(v):
            out = []
            while v != s and parent[v] is not None:
                u, k, sg = parent[v]; out.append((k, sg)); v = u
            return out

        q0 = np.zeros(nb)
        for k, sg in path(t):
            q0[k] += sg
        chords = [k for k in range(nb) if not intree[k] and seen[fr[k]] and seen[tt[k]]]
        C = np.zeros((len(chords), nb))
        for j, k in enumerate(chords):
            C[j, k] = 1.0
            for kk, sg in path(tt[k]):
                C[j, kk] -= sg
            for kk, sg in path(fr[k]):
                C[j, kk] += sg
        self.q0 = q0; self.C = C

    def solve(self, R, m0=None):
        C = self.C; q0 = self.q0
        if C.shape[0] == 0:
            q = q0.copy(); return q, float(np.sum(R * np.abs(q) ** 3)), np.zeros(0)
        m = np.zeros(C.shape[0]) if m0 is None else m0.copy()
        scale = max(np.max(R), 1e-12)

        def content(mm):
            qq = q0 + C.T @ mm
            return np.sum(R * np.abs(qq) ** 3) / 3

        f = content(m)
        for it in range(300):
            q = q0 + C.T @ m
            g = C @ (R * q * np.abs(q))
            D = 2 * R * np.maximum(np.abs(q), 1e-9) + 1e-14 * scale
            H = (C * D) @ C.T
            try:
                dm = -np.linalg.solve(H, g)
            except np.linalg.LinAlgError:
                dm = -np.linalg.lstsq(H, g, rcond=None)[0]
            t = 1.0
            gd = float(g @ dm)
            while True:
                fn = content(m + t * dm)
                if fn <= f + 1e-4 * t * gd or t < 1e-10:
                    break
                t *= 0.5
            m = m + t * dm
            f = fn
            if np.max(np.abs(t * dm)) < 1e-13 and it > 0:
                break
        q = q0 + C.T @ m
        Req = float(np.sum(R * np.abs(q) ** 3))
        return q, Req, m


# ----------------------------------------------------------------------------- fans
class Fan:
    """Catalogue characteristic (piecewise linear) less the ducting loss: E(q) = P(q) - Rd q|q|."""

    def __init__(self, x, p, Rd):
        o = np.argsort(np.asarray(x, float), kind='stable')
        x = np.asarray(x, float)[o]; p = np.asarray(p, float)[o]
        keep = np.concatenate([[True], np.diff(x) > 1e-12])
        x = x[keep]; p = p[keep]
        self.x = x; self.p = p; self.Rd = max(float(Rd), 0.0)
        self.m = np.diff(p) / np.diff(x)
        self.qmax = x[-1]
        el = []
        for k in range(len(x) - 1):
            pts = [x[k], x[k + 1]]
            if self.Rd > 0:
                qs = self.m[k] / (2 * self.Rd)
                if x[k] + 1e-9 < qs < x[k + 1] - 1e-9:
                    pts = [x[k], qs, x[k + 1]]
            for a, b in zip(pts[:-1], pts[1:]):
                mid = 0.5 * (a + b)
                sg = 1 if (self.m[k] - 2 * self.Rd * abs(mid)) > 0 else -1
                el.append((a, b, k, sg))
        pieces = []
        for e in el:
            if pieces and pieces[-1]['sign'] == e[3]:
                pieces[-1]['el'].append(e); pieces[-1]['qb'] = e[1]
            else:
                pieces.append({'sign': e[3], 'el': [e], 'qa': e[0], 'qb': e[1]})
        for pc in pieces:
            ea, eb = self.E(pc['qa']), self.E(pc['qb'])
            pc['slo'], pc['shi'] = min(ea, eb), max(ea, eb)
            pc['brk'] = sorted(set(self.Ek(k, z) for a, b, k, sg in pc['el'] for z in (a, b)))
        self.pieces = pieces

    def seg(self, q):
        k = int(np.searchsorted(self.x, q, side='right')) - 1
        return min(max(k, 0), len(self.x) - 2)

    def Ek(self, k, q):
        return self.p[k] + self.m[k] * (q - self.x[k]) - self.Rd * q * abs(q)

    def E(self, q):
        return self.Ek(self.seg(q), q)

    def inv(self, j, s):
        """flow on monotone piece j at which E = s"""
        pc = self.pieces[j]
        best = None
        for a, b, k, sg in pc['el']:
            ea = self.Ek(k, a); eb = self.Ek(k, b)
            lo, hi = (ea, eb) if ea <= eb else (eb, ea)
            if lo - 1e-9 <= s <= hi + 1e-9:
                mk = self.m[k]; Rd = self.Rd
                c0 = self.p[k] - mk * self.x[k] - s
                if Rd <= 0:
                    q = -c0 / mk if mk != 0 else 0.5 * (a + b)
                else:
                    disc = max(mk * mk + 4 * Rd * c0, 0.0)
                    sq = math.sqrt(disc)
                    r1 = (mk - sq) / (2 * Rd); r2 = (mk + sq) / (2 * Rd)
                    mid = 0.5 * (a + b)
                    c1 = a - 1e-7 <= r1 <= b + 1e-7; c2 = a - 1e-7 <= r2 <= b + 1e-7
                    if c1 and not c2:
                        q = r1
                    elif c2 and not c1:
                        q = r2
                    else:
                        q = r1 if abs(r1 - mid) <= abs(r2 - mid) else r2
                return min(max(q, a), b)
        # outside: nearest end
        if abs(s - self.E(pc['qa'])) <= abs(s - self.E(pc['qb'])):
            return pc['qa']
        return pc['qb']

    def slope(self, j, q):
        pc = self.pieces[j]
        for a, b, k, sg in pc['el']:
            if a - 1e-9 <= q <= b + 1e-9:
                # interior slope of this piece
                qq = min(max(q, a + 1e-9 * (b - a)), b - 1e-9 * (b - a))
                return self.m[k] - 2 * self.Rd * abs(qq)
        k = pc['el'][0][2] if q < pc['qa'] else pc['el'][-1][2]
        return self.m[k] - 2 * self.Rd * abs(q)


class Segment:
    def __init__(self, fs, combo, sa, sb):
        self.fs = fs; self.c = combo; self.sa = sa; self.sb = sb
        self.Ra = fs.Rof(combo, sa); self.Rb = fs.Rof(combo, sb)
        self.Rmin = min(self.Ra, self.Rb); self.Rmax = max(self.Ra, self.Rb)
        self.Qa = fs.eval(combo, sa)[1]; self.Qb = fs.eval(combo, sb)[1]

    def contains(self, R, tol=1e-12):
        return self.Rmin * (1 - tol) <= R <= self.Rmax * (1 + tol)

    def s_at(self, R):
        R = min(max(R, self.Rmin), self.Rmax)
        a, b = self.sa, self.sb
        fa = self.fs.Rof(self.c, a) - R
        if fa == 0:
            return a
        for _ in range(200):
            mid = 0.5 * (a + b)
            fm = self.fs.Rof(self.c, mid) - R
            if (fm > 0) == (fa > 0):
                a, fa = mid, fm
            else:
                b = mid
            if b - a <= 1e-13 * max(1.0, abs(a)):
                break
        return 0.5 * (a + b)

    def state(self, R):
        s = self.s_at(R)
        q, Q, _ = self.fs.eval(self.c, s)
        return s, q, Q


class FanSystem:
    def __init__(self, fans):
        self.fans = fans; self.n = len(fans)
        self.segs = []
        self.jcache = {}
        self._build()

    def srange(self, c):
        lo = max(f.pieces[j]['slo'] for f, j in zip(self.fans, c))
        hi = min(f.pieces[j]['shi'] for f, j in zip(self.fans, c))
        return lo, hi

    def eval(self, c, s):
        q = np.array([f.inv(j, s) for f, j in zip(self.fans, c)])
        Q = float(q.sum())
        return q, Q, (s / (Q * Q) if Q > 0 else float('inf'))

    def Rof(self, c, s):
        Q = sum(f.inv(j, s) for f, j in zip(self.fans, c))
        return s / (Q * Q) if Q > 0 else float('inf')

    def stab(self, c, s):
        """largest eigenvalue of diag(e) - r 11^T (negative = stable)"""
        q, Q, R = self.eval(c, s)
        if Q <= 0 or s <= 0:
            return 1.0
        e = np.array([f.slope(j, qi) for f, j, qi in zip(self.fans, c, q)])
        r = 2 * s / Q
        M = np.diag(e) - r
        return float(np.max(np.linalg.eigvalsh(M)))

    def _build(self):
        import itertools
        for c in itertools.product(*[range(len(f.pieces)) for f in self.fans]):
            lo, hi = self.srange(c)
            if not hi > lo + 1e-9:
                continue
            lo = max(lo, 1e-9)
            if not hi > lo:
                continue
            bps = {lo, hi}
            for f, j in zip(self.fans, c):
                for v in f.pieces[j]['brk']:
                    if lo < v < hi:
                        bps.add(v)
            bps = sorted(bps)
            # sample stability inside each sub-interval
            pts = []
            for a, b in zip(bps[:-1], bps[1:]):
                if b - a < 1e-12:
                    continue
                ns = 24
                for i in range(ns + 1):
                    t = i / ns
                    sx = a + (b - a) * (1e-9 + t * (1 - 2e-9))
                    pts.append(sx)
            if not pts:
                continue
            st = [self.stab(c, sx) < 0 for sx in pts]
            # segments of consecutive stable samples, boundaries refined by bisection
            i = 0
            while i < len(pts):
                if not st[i]:
                    i += 1; continue
                j = i
                while j + 1 < len(pts) and st[j + 1]:
                    j += 1
                sa = pts[i] if i == 0 else self._bis(c, pts[i - 1], pts[i])
                sb = pts[j] if j == len(pts) - 1 else self._bis(c, pts[j + 1], pts[j])
                if i == 0:
                    sa = lo
                if j == len(pts) - 1:
                    sb = hi
                if sb > sa:
                    # keep away from a point with no airflow at all (every fan at shutoff)
                    for _ in range(40):
                        if np.isfinite(self.Rof(c, sb)) or sb <= sa:
                            break
                        sb = sb - 1e-6 * max(hi - lo, 1e-6)
                    seg = Segment(self, c, sa, sb)
                    if np.isfinite(seg.Rmin) and np.isfinite(seg.Rmax) and seg.Rmax > seg.Rmin:
                        self.segs.append(seg)
                i = j + 1

    def _bis(self, c, su, ss):
        """boundary between unstable su and stable ss"""
        a, b = su, ss
        for _ in range(100):
            mid = 0.5 * (a + b)
            if self.stab(c, mid) < 0:
                b = mid
            else:
                a = mid
            if abs(b - a) < 1e-12 * max(1, abs(b)):
                break
        return b

    # ---- dynamics
    def relax(self, q0, R):
        fans = self.fans

        def f(t, q):
            E = np.array([fn.E(qi) for fn, qi in zip(fans, q)])
            Q = q.sum()
            return E - R * Q * abs(Q)

        from scipy.integrate import solve_ivp
        q = np.array(q0, float); t0 = 0.0; dt = 1.0
        for _ in range(40):
            sol = solve_ivp(f, (t0, t0 + dt), q, method='LSODA', rtol=1e-9, atol=1e-9)
            q = sol.y[:, -1]; t0 += dt
            if np.max(np.abs(f(0, q))) < 1e-6 and (np.max(np.abs(q - q0)) > 1e-3 or t0 > 60):
                break
            dt *= 2
        return q

    def candidates(self, R, exclude=None):
        return [i for i, sg in enumerate(self.segs) if i != exclude and sg.contains(R, 1e-9)]

    def jump(self, sid, end):
        key = (sid, end)
        if key in self.jcache:
            return self.jcache[key]
        sg = self.segs[sid]
        if end == 'max':
            s_e = sg.sa if sg.Ra >= sg.Rb else sg.sb; d = 1
        else:
            s_e = sg.sa if sg.Ra <= sg.Rb else sg.sb; d = -1
        qe, Qe, Re = self.eval(sg.c, s_e)
        Rn = Re * (1 + 1e-6 * d)
        qs = self.relax(qe, Rn)
        cands = self.candidates(Rn, exclude=sid)
        best = None; bd = None
        for i in cands:
            s, q, Q = self.segs[i].state(Rn)
            dist = float(np.max(np.abs(q - qs)))
            if bd is None or dist < bd:
                best, bd = i, dist
        if best is None:
            best = sid
        dbg('  jump from seg', sid, sg.c, 'at R=%.6f' % Re, 'q', np.round(qe, 2), '->', best,
            self.segs[best].c, 'q', np.round(qs, 2), 'dist %.3g' % (bd if bd is not None else -1))
        self.jcache[key] = best
        return best

    def step(self, sid, Rprev, Rt):
        d = 1 if Rt > Rprev else -1
        for _ in range(60):
            sg = self.segs[sid]
            if sg.contains(Rt):
                return sid
            if d > 0 and Rt > sg.Rmax:
                nid = self.jump(sid, 'max')
            elif d < 0 and Rt < sg.Rmin:
                nid = self.jump(sid, 'min')
            else:
                return sid
            if nid == sid:
                return sid
            sid = nid
        return sid


# ----------------------------------------------------------------------------- package
class Package:
    def __init__(self, pkg):
        self.dir = pkg
        J = os.path.join
        try:
            self.district = json.load(open(J(pkg, 'district.json')))
        except Exception:
            self.district = {}
        self.allow = int(fnum(self.district.get('survey_allowance', 0), 0) or 0)
        self.branches = read_csv(J(pkg, 'branches.csv'))
        self.surveys = read_csv(J(pkg, 'surveys.csv'))
        self.work = read_csv(J(pkg, 'work_log.csv'))
        self.regs = read_csv(J(pkg, 'regulators.csv'))
        self.doors = read_csv(J(pkg, 'doors.csv'))
        self.fans = read_csv(J(pkg, 'fans.csv'))
        self.curves = read_csv(J(pkg, 'fan_curves.csv'))
        self.log = read_csv(J(pkg, 'log.csv'))
        self.points = read_csv(J(pkg, 'points.csv'))
        for r in self.branches:
            r['kind'] = r.get('kind', '').lower()
        self.B = {r['branch']: r for r in self.branches}
        # regulator tables
        self.regtab = {}
        for r in self.regs:
            v = fnum(r.get('resistance_Ns2_m8')); st = fnum(r.get('setting'))
            if v is None or st is None:
                continue
            self.regtab.setdefault(r['regulator'], {})[st] = v
        self.doortab = {}
        for r in self.doors:
            self.doortab[r['door']] = [fnum(r.get('resistance_closed_Ns2_m8')), fnum(r.get('resistance_open_Ns2_m8'))]

    def reg_R(self, item, setting):
        tab = self.regtab.get(item)
        st = fnum(setting)
        if not tab or st is None:
            return None
        if st in tab:
            return tab[st]
        ks = sorted(tab)
        if st <= ks[0]:
            return tab[ks[0]]
        if st >= ks[-1]:
            return tab[ks[-1]]
        lo = max(k for k in ks if k <= st); hi = min(k for k in ks if k >= st)
        t = (st - lo) / (hi - lo)
        return math.exp((1 - t) * math.log(tab[lo]) + t * math.log(tab[hi]))


def campaigns(surveys):
    dates = sorted(set(r['date'] for r in surveys))
    out = []; cur = []
    for d in dates:
        if cur and (pdate(d) - pdate(cur[-1])).days > 7:
            out.append(cur); cur = []
        cur.append(d)
    if cur:
        out.append(cur)
    return out


def campaign_checks(P):
    """Stoppings (and closed doors) whose campaign leakage contradicts their register value.
    returns {branch: (R_estimate, rel_sigma, campaign_index, leak)}"""
    br = P.branches
    camps = campaigns(P.surveys)
    nodes = sorted(set(r['from_node'] for r in br) | set(r['to_node'] for r in br))
    ni = {n: i for i, n in enumerate(nodes)}
    inc = {}
    for r in br:
        inc.setdefault(r['from_node'], []).append((r['branch'], -1))
        inc.setdefault(r['to_node'], []).append((r['branch'], +1))
    found = {}
    hist = {}
    for ci, cd in enumerate(camps):
        cds = set(cd)
        S = {}
        for r in sorted(P.surveys, key=lambda r: r['date']):
            if r['date'] in cds and r['branch'] in P.B and P.B[r['branch']]['kind'] == 'airway':
                dp = fnum(r.get('dp_Pa')); q = fnum(r.get('q_m3_s'))
                if dp is not None and q is not None:
                    S[r['branch']] = (dp, q)
        if len(S) < 3:
            continue
        rows = []
        for b, (dp, q) in S.items():
            rows.append((ni[P.B[b]['from_node']], ni[P.B[b]['to_node']], dp, 1.0 / (0.003 * abs(dp) + 1e-3)))
        par = list(range(len(nodes)))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]; x = par[x]
            return x

        for a, b, _, _ in rows:
            par[find(a)] = find(b)
        A = np.zeros((len(rows) + len(nodes), len(nodes))); y = np.zeros(len(rows) + len(nodes))
        for k, (a, b, dp, w) in enumerate(rows):
            A[k, a] = w; A[k, b] = -w; y[k] = dp * w
        seenroot = set()
        for n in range(len(nodes)):
            rt = find(n)
            if rt not in seenroot:
                seenroot.add(rt); A[len(rows) + n, n] = 1e-6
        p = np.linalg.lstsq(A, y, rcond=None)[0]
        flow = {b: q for b, (dp, q) in S.items()}
        bound = {b: 0.003 * abs(q) for b, (dp, q) in S.items()}
        for _ in range(len(nodes)):
            est = {}
            for n, lst in inc.items():
                if n == 'ATM':
                    continue
                unk = [(b, s) for b, s in lst if b not in flow]
                if len(unk) != 1:
                    continue
                b0, s0 = unk[0]
                tot = sum(s * flow[b] for b, s in lst if b in flow)
                bd = sum(bound[b] for b, s in lst if b in flow)
                est.setdefault(b0, []).append((-tot * s0, bd))
            if not est:
                break
            for b, e in est.items():
                flow[b] = sum(x[0] for x in e) / len(e); bound[b] = sum(x[1] for x in e) / len(e)
        for b, r in P.B.items():
            if r['kind'] not in ('stopping', 'door') or b not in flow or b in S:
                continue
            a_, b_ = ni[r['from_node']], ni[r['to_node']]
            if find(a_) != find(b_):
                continue
            dp = p[a_] - p[b_]; q = flow[b]; bd = bound[b] + 0.02
            if r['kind'] == 'stopping':
                R0 = fnum(r.get('resistance_Ns2_m8'))
                if not R0 or R0 <= 0:
                    continue
                qe = math.copysign(math.sqrt(abs(dp) / R0), dp)
                z = abs(q - qe) / bd
                dbg('campaign', ci, b, 'leak %.3f reg %.3f bound %.3f z %.2f' % (q, qe, bd, z))
                flag = z > 1.5 and abs(q) > 2 * bd and q * dp > 0
                hist.setdefault(b, []).append((ci, flag, dp / (q * abs(q)) if flag else None,
                                              2 * bd / abs(q) / math.sqrt(3) if q else None, q))
            else:
                rc, ro = P.doortab.get(r.get('item'), [None, None])
                if not rc or not ro:
                    continue
                qc = math.copysign(math.sqrt(abs(dp) / rc), dp); qo = math.copysign(math.sqrt(abs(dp) / ro), dp)
                zc = abs(q - qc) / bd; zo = abs(q - qo) / bd
                dbg('campaign', ci, b, 'door leak %.3f closed %.3f open %.3f bound %.3f' % (q, qc, qo, bd))
                # a closed door leaking well beyond its closed value, far from open
                flag = (zc > 1.5 and zo > 1.5 and abs(q) > 2 * bd and q * dp > 0 and abs(q) < abs(qo) * 0.5
                        and abs(q) > abs(qc))
                hist.setdefault('door:' + b, []).append((ci, flag, dp / (q * abs(q)) if flag else None,
                                                         2 * bd / abs(q) / math.sqrt(3) if q else None, q))
        # refine the leakage of the suspect items: constrained least squares over the whole campaign
        # with the intact stoppings held near their register leakage
        sus = [k for k, h in hist.items() if h and h[-1][0] == ci and h[-1][1]]
        if sus:
            try:
                ref = refine_leaks(P, S, p, ni, find, [k[5:] if k.startswith('door:') else k for k in sus])
                for k in sus:
                    b = k[5:] if k.startswith('door:') else k
                    if b in ref:
                        xq, xs = ref[b]
                        r = P.B[b]; dp = p[ni[r['from_node']]] - p[ni[r['to_node']]]
                        if xq * dp > 0:
                            old = hist[k][-1]
                            hist[k][-1] = (ci, True, dp / (xq * abs(xq)), 2 * xs / abs(xq) + 0.003, xq)
                            dbg('refined', k, 'campaign', ci, 'leak %.3f -> %.3f (sd %.3f)' % (old[4], xq, xs))
            except Exception as e:  # keep the local estimates
                dbg('refine failed', e)
    # an item counts as damaged when the latest campaign that shows it says so; its resistance is
    # pooled over the run of campaigns before that agree with it
    for key, h in hist.items():
        h.sort(key=lambda x: x[0])
        if not h[-1][1]:
            continue
        lnl = math.log(h[-1][2]); sl = h[-1][3]
        num = 0.0; den = 0.0; used = 0
        for ci, flag, Rc, sc, q in reversed(h):
            if not flag or abs(math.log(Rc) - lnl) > 2.5 * math.hypot(sc, sl):
                break
            num += math.log(Rc) / sc ** 2; den += 1 / sc ** 2; used += 1
        found[key] = (math.exp(num / den), 1 / math.sqrt(den), h[-1][0], h[-1][4])
        dbg('damaged', key, 'campaign estimates', [(round(x[2], 3) if x[2] else None) for x in h], 'pooled over', used)
    return found


def refine_leaks(P, S, p, ni, find, suspects):
    """flows of the suspect stoppings/doors from all airway readings of one campaign"""
    br = P.branches
    nb = len(br); bidx = {r['branch']: j for j, r in enumerate(br)}
    nodes = sorted(ni, key=lambda n: ni[n])
    Aeq = np.zeros((len(nodes), nb))
    for j, r in enumerate(br):
        Aeq[ni[r['from_node']], j] -= 1.0; Aeq[ni[r['to_node']], j] += 1.0
    keep = [i for i, n in enumerate(nodes) if n != 'ATM']
    Aeq = Aeq[keep]
    m = np.zeros(nb); w = np.full(nb, 1e-10); sd = np.zeros(nb)
    sus = set(suspects)
    for j, r in enumerate(br):
        b = r['branch']
        if b in S:
            q = S[b][1]; sd[j] = 0.003 * abs(q) / math.sqrt(3) + 1e-4
            m[j] = q; w[j] = 1 / sd[j] ** 2
        elif r['kind'] == 'stopping' and b not in sus:
            a_, b_ = ni[r['from_node']], ni[r['to_node']]
            R0 = fnum(r.get('resistance_Ns2_m8'))
            if R0 and R0 > 0 and find(a_) == find(b_):
                dp = p[a_] - p[b_]
                mm = math.copysign(math.sqrt(abs(dp) / R0), dp)
                sd[j] = 0.02 * abs(mm) + 0.01
                m[j] = mm; w[j] = 1 / sd[j] ** 2
    nc = Aeq.shape[0]
    K = np.zeros((nb + nc, nb + nc))
    K[:nb, :nb] = np.diag(2 * w); K[:nb, nb:] = Aeq.T; K[nb:, :nb] = Aeq
    Kinv = np.linalg.pinv(K, rcond=1e-14)
    G = Kinv[:nb, :nb] * (2 * w)[None, :]
    x = G @ m
    out = {}
    for b in suspects:
        j = bidx[b]
        var = float(np.sum((G[j] * sd) ** 2))
        out[b] = (float(x[j]), math.sqrt(var))
    return out


def curve_points(curves, model, blade):
    """catalogue table of a model at a blade setting (nearest setting if the exact one is missing)"""
    rows = [c for c in curves if c.get('model') == model] or list(curves)
    def pick(bl):
        out = [(fnum(c.get('flow_m3_s')), fnum(c.get('pressure_Pa'))) for c in rows
               if c.get('blade_setting') == bl or (fnum(c.get('blade_setting')) is not None
                                                   and fnum(c.get('blade_setting')) == fnum(bl))]
        return [x for x in out if x[0] is not None and x[1] is not None]
    pts = pick(blade)
    if len(pts) < 2:
        bls = sorted(set(c.get('blade_setting') for c in rows),
                     key=lambda b: abs((fnum(b) or 0) - (fnum(blade) or 0)))
        for bl in bls:
            pts = pick(bl)
            if len(pts) >= 2:
                break
    return pts


# ----------------------------------------------------------------------------- model
class Model:
    def __init__(self, P):
        self.P = P
        br = P.branches
        self.fanbr = [r for r in br if r['kind'] == 'fan']
        self.passive = [r for r in br if r['kind'] != 'fan']
        if not self.fanbr:
            raise RuntimeError('no fan')
        F = self.fanbr[0]['from_node']; T = self.fanbr[0]['to_node']
        self.F, self.T = F, T
        self.net = Network([r['branch'] for r in self.passive], [r['from_node'] for r in self.passive],
                           [r['to_node'] for r in self.passive], T, F)
        self.pidx = {r['branch']: i for i, r in enumerate(self.passive)}
        self.fidx = {r['branch']: i for i, r in enumerate(self.fanbr)}
        # fans
        fanrow = {}
        for r in P.fans:
            fanrow[r.get('branch', '')] = r
            fanrow['item:' + r.get('fan', '')] = r
        fans = []
        for r in self.fanbr:
            fr = fanrow.get(r['branch']) or fanrow.get('item:' + r.get('item', ''))
            model = fr['model']; blade = fr['blade_setting']
            pts = curve_points(P.curves, model, blade)
            fans.append(Fan([x[0] for x in pts], [x[1] for x in pts], fnum(r.get('resistance_Ns2_m8'), 0.0) or 0.0))
        self.fans = fans
        self.fs = FanSystem(fans)
        self._states()

    def _states(self):
        P = self.P
        rows = [r for r in P.log if r.get('time')]
        rows.sort(key=lambda r: r['time'])
        t0 = rows[0]['time'] if rows else ''
        init = {}
        for r in rows:
            if r['time'] == t0:
                init[r['item']] = r['setting']
        for r in rows:            # items never set at the first time: earliest mention
            init.setdefault(r['item'], r['setting'])
        st = []
        cur = dict(init)
        st.append((t0, dict(cur)))
        for r in rows:
            if r['time'] == t0:
                continue
            cur[r['item']] = r['setting']
            st.append((r['time'], dict(cur)))
        self.states = st

    def Rvec(self, Rair, Rstop, settings, Rdoor_closed):
        P = self.P
        R = np.zeros(len(self.passive))
        for i, r in enumerate(self.passive):
            k = r['kind']; b = r['branch']
            if k == 'airway':
                R[i] = Rair[b]
            elif k == 'stopping':
                R[i] = Rstop.get(b, fnum(r.get('resistance_Ns2_m8'), 1e4))
            elif k == 'regulator':
                v = P.reg_R(r.get('item'), settings.get(r.get('item')))
                R[i] = v if v is not None else 0.0
            elif k == 'door':
                item = r.get('item'); stt = str(settings.get(item, 'closed')).lower()
                rc, ro = P.doortab.get(item, [None, None])
                rc = Rdoor_closed.get(b, rc)
                R[i] = (ro if stt.startswith('o') else rc) or 0.0
            else:
                R[i] = fnum(r.get('resistance_Ns2_m8'), 0.0) or 0.0
        return np.maximum(R, 1e-12)

    def solve_states(self, Rair, Rstop, Rdoor_closed):
        out = []
        m = None
        cache = {}
        for t, sett in self.states:
            R = self.Rvec(Rair, Rstop, sett, Rdoor_closed)
            key = R.tobytes()
            if key in cache:
                out.append(cache[key]); continue
            q, Req, m = self.net.solve(R, m)
            w = R * np.abs(q) ** 3 / Req
            res = (Req, q, w)
            cache[key] = res
            out.append(res)
        return out


def track(fs, lnR, init_sid):
    sid = init_sid
    sig = [sid]
    R = np.exp(lnR)
    for k in range(1, len(R)):
        sid = fs.step(sid, R[k - 1], R[k])
        sig.append(sid)
    return tuple(sig)


def initial_segments(fs, R0):
    c = fs.candidates(R0)
    if not c:
        # nearest segment by R
        c = [min(range(len(fs.segs)), key=lambda i: min(abs(math.log(fs.segs[i].Rmin / R0)),
                                                       abs(math.log(fs.segs[i].Rmax / R0))))]
    # prefer the state with the largest total flow (all fans unstalled)
    c.sort(key=lambda i: -fs.segs[i].state(R0)[2])
    return c


def sample_paths(fs, lnR0, W, sig_kind, nsamp, rng, mult=1.0, init_choices=None):
    """Monte-Carlo over survey errors: returns dict signature -> weight"""
    B = W.shape[1]
    counts = {}
    nominal_init = initial_segments(fs, math.exp(lnR0[0]))
    inits = init_choices or nominal_init
    prior = [0.85] + [0.15 / max(1, len(inits) - 1)] * (len(inits) - 1) if len(inits) > 1 else [1.0]
    # nominal path
    sig0 = track(fs, lnR0, inits[0])
    counts[sig0] = counts.get(sig0, 0) + 1e-6
    if nsamp <= 0:
        return counts, sig0
    D = np.zeros((nsamp, B))
    for b in range(B):
        kind, par = sig_kind[b]
        if kind == 'survey':
            e1 = rng.uniform(-0.003, 0.003, nsamp); e2 = rng.uniform(-0.003, 0.003, nsamp)
            D[:, b] = (np.log1p(e1) - 2 * np.log1p(e2)) * mult
        elif kind == 'normal':
            D[:, b] = rng.normal(0, par * mult, nsamp)
    dln = D @ W.T
    for i in range(nsamp):
        lnR = lnR0 + dln[i]
        R0 = math.exp(lnR[0])
        if len(inits) > 1:
            for ii, wgt in zip(inits, prior):
                if fs.segs[ii].contains(R0, 1e-6) or ii == inits[0]:
                    sig = track(fs, lnR, ii)
                    counts[sig] = counts.get(sig, 0) + wgt
        else:
            ii = inits[0]
            sig = track(fs, lnR, ii)
            counts[sig] = counts.get(sig, 0) + 1
    return counts, sig0


# ----------------------------------------------------------------------------- main
def run(pkg, out_csv):
    P = Package(pkg)
    M = Model(P)
    fs = M.fs
    dbg('segments:')
    for i, sg in enumerate(fs.segs):
        dbg('  ', i, sg.c, 'R [%.6f, %.6f]' % (sg.Rmin, sg.Rmax), 'Q [%.2f, %.2f]' % (sg.Qa, sg.Qb))

    # --- airway resistances from surveys
    surv = {}
    for r in P.surveys:
        b = r.get('branch')
        if b not in P.B:
            continue
        dp = fnum(r.get('dp_Pa')); q = fnum(r.get('q_m3_s'))
        if dp is None or q is None or q == 0 or dp == 0 or dp * q < 0:
            continue
        surv.setdefault(b, []).append((r['date'], dp / (q * abs(q))))
    for b in surv:
        surv[b].sort(key=lambda x: x[0])
    airways = [r['branch'] for r in P.branches if r['kind'] == 'airway']
    lastwork = {}
    for w in P.work:
        if w.get('work', '').upper() in ('RESUPPORTED', 'ENLARGED'):
            b = w.get('branch')
            if b not in lastwork or w['date'] > lastwork[b]:
                lastwork[b] = w['date']
    Rair = {}; akind = {}
    must = []; maybe = []
    allR = [v[-1][1] for v in surv.values()]
    medR = float(np.median(allR)) if allR else 0.01
    FALLBACK = 0.64
    for b in airways:
        if b not in surv:
            Rair[b] = medR; akind[b] = ('normal', 1.0); must.append(b); continue
        d_last, R_last = surv[b][-1]
        Rair[b] = R_last; akind[b] = ('survey', None)
        if b in lastwork:
            wd = lastwork[b]
            if wd > d_last:
                Rair[b] = R_last * FALLBACK; akind[b] = ('normal', 0.15); must.append(b)
            elif wd == d_last:
                prev = [x[1] for x in surv[b][:-1]]
                if not prev or R_last / prev[-1] > 0.9:
                    # same day as the work and no sign of the work in the reading
                    if prev:
                        Rair[b] = R_last * FALLBACK
                    akind[b] = ('normal', 0.15)
                    maybe.append(b)
    dbg('must', must, 'maybe', maybe)

    # --- stoppings / doors from the campaigns
    try:
        dmg = campaign_checks(P)
    except Exception as e:
        dbg('campaign checks failed', repr(e)); dmg = {}
    Rstop = {}; Rdoor = {}; skind = {}
    for k, (Rest, rs, ci, q) in dmg.items():
        if k.startswith('door:'):
            Rdoor[k[5:]] = Rest; skind[k[5:]] = ('normal', max(rs, 0.01))
        else:
            Rstop[k] = Rest; skind[k] = ('normal', max(rs, 0.01))
    dbg('damaged', dmg)

    def kinds():
        out = []
        for r in M.passive:
            b = r['branch']
            if r['kind'] == 'airway':
                out.append(akind[b])
            elif b in skind:
                out.append(skind[b])
            else:
                out.append(('none', None))
        return out

    rng = np.random.default_rng(12345)

    def analyse(nsamp, mult=1.0):
        sol = M.solve_states(Rair, Rstop, Rdoor)
        lnR = np.log(np.array([s[0] for s in sol]))
        W = np.array([s[2] for s in sol])
        try:
            counts, sig0 = sample_paths(fs, lnR, W, kinds(), nsamp, rng, mult)
        except Exception as e:
            dbg('sampling failed', repr(e))
            counts, sig0 = sample_paths(fs, lnR, W, kinds(), 0, rng, mult)
        return sol, lnR, counts, sig0

    sol, lnR, counts, sig0 = analyse(300)
    tot = sum(counts.values())
    finals = {}
    for sig, c in counts.items():
        finals[sig[-1]] = finals.get(sig[-1], 0) + c
    pfin = {k: v / tot for k, v in finals.items()}
    dbg('pre-analysis: nominal final', sig0[-1], 'final distribution', pfin, 'n signatures', len(counts))
    uncertain = sum(v for k, v in pfin.items() if k != sig0[-1]) > 0.01

    # --- the survey order
    Rfin = math.exp(lnR[-1])
    fan_choice = None
    if fs.segs:
        cands = sorted(pfin, key=lambda k: -pfin[k])
        best = None
        for i, r in enumerate(M.fanbr):
            qs = [fs.segs[k].state(Rfin)[1][i] for k in cands]
            sep = min([abs(a - b) / max(a, b, 1e-6) for ii, a in enumerate(qs) for b in qs[ii + 1:]] or [1.0])
            if best is None or sep > best[0]:
                best = (sep, r['branch'])
        fan_choice = best[1]
    allow = max(P.allow, 0)
    need = must + [b for b in maybe if b not in must]
    p_alt = sum(v for k, v in pfin.items() if k != sig0[-1])
    if len(need) + (1 if uncertain else 0) > allow and need:
        try:
            need = rank_by_impact(M, sol, Rair, Rstop, Rdoor, need)
        except Exception as e:
            dbg('ranking failed', repr(e))
    order = []
    if fan_choice and p_alt > 0.03 and allow > 0:
        # the present state of the fans settles which history the district went through
        order = need[:allow - 1] + [fan_choice]
    else:
        order = need[:allow]
    for k in sorted(dmg, key=lambda k: -abs(dmg[k][3])):
        b = k[5:] if k.startswith('door:') else k
        if len(order) < allow and b not in order:
            if k.startswith('door:'):
                # only useful when the door stands closed now
                it = P.B[b].get('item'); stt = str(M.states[-1][1].get(it, 'closed')).lower()
                if stt.startswith('o'):
                    continue
            order.append(b)
    if fan_choice and fan_choice not in order and len(order) < allow:
        order.append(fan_choice)
    dbg('order', order)

    meas = {}
    if order:
        meas = place_order(pkg, order)
    dbg('survey result', meas)

    # --- use the readings
    fan_meas = {}
    for b, (dp, q) in meas.items():
        r = P.B.get(b)
        if r is None:
            continue
        if r['kind'] == 'airway' and q != 0 and dp * q > 0:
            Rair[b] = dp / (q * abs(q)); akind[b] = ('survey', None)
        elif r['kind'] == 'stopping' and q != 0 and dp * q > 0:
            Rstop[b] = dp / (q * abs(q)); skind[b] = ('survey', None)
        elif r['kind'] == 'door' and q != 0 and dp * q > 0:
            it = r.get('item'); stt = str(M.states[-1][1].get(it, 'closed')).lower()
            if b in Rdoor and not stt.startswith('o'):
                Rdoor[b] = dp / (q * abs(q)); skind[b] = ('survey', None)
        elif r['kind'] == 'fan':
            fan_meas[b] = (dp, q)
    for b in must:
        if b not in meas:
            dbg('no survey for', b, '- fallback estimate used')

    sol, lnR, counts, sig0 = analyse(400)
    if DEBUG:
        tot = sum(counts.values()); fin = {}
        for sig, c in counts.items():
            fin[sig[-1]] = fin.get(sig[-1], 0) + c / tot
        dbg('post-analysis final distribution', fin, 'signatures', len(counts))
        for sig, c in sorted(counts.items(), key=lambda x: -x[1])[:6]:
            dif = [i for i, (a, b) in enumerate(zip(sig, sig0)) if a != b]
            dbg('   sig weight %.3f' % (c / tot), 'differs from nominal at states', dif[:3], '...', len(dif))
    chosen = sig0
    if fan_meas:
        Rfin = math.exp(lnR[-1])

        def mismatch(sid):
            sv, q, Q = fs.segs[sid].state(Rfin)
            worst = 0.0
            for b, (dp, qm) in fan_meas.items():
                i = M.fidx[b]
                worst = max(worst, abs(q[i] - qm) / max(abs(qm), 1.0), abs(sv + dp) / max(abs(dp), 1.0))
            return worst

        allm = {i: mismatch(i) for i, sg in enumerate(fs.segs) if sg.contains(Rfin, 0.02)}
        okset = set()
        if allm:
            bestm = min(allm.values())
            dbg('fan survey mismatch per final state', {fs.segs[i].c: round(v, 4) for i, v in allm.items()})
            if bestm < 0.06:
                okset = {i for i, v in allm.items() if v <= bestm + 0.01}
        good = None
        if okset:
            for mult in (1.0, 2.0, 4.0, 8.0):
                if mult > 1.0:
                    _, _, c2, _ = analyse(400, mult)
                    for k, v in c2.items():
                        counts[k] = counts.get(k, 0) + v * 1e-3   # wider spread: lower weight
                cons = {k: v for k, v in counts.items() if k[-1] in okset}
                if cons:
                    good = cons
                    break
        if good:
            chosen = max(good, key=lambda k: (good[k], k == sig0))
        else:
            dbg('fan survey matches no sampled history; most likely history kept')
            chosen = max(counts, key=lambda k: (counts[k], k == sig0))
    else:
        chosen = max(counts, key=lambda k: (counts[k], k == sig0))
    dbg('chosen differs from nominal at', [i for i, (a, b) in enumerate(zip(chosen, sig0)) if a != b])

    # --- results
    times = [t for t, _ in M.states]
    st_res = []
    for k, (Req, qu, w) in enumerate(sol):
        s, qf, Q = fs.segs[chosen[k]].state(Req)
        st_res.append((qf, Q, qu))
        dbg(times[k], fs.segs[chosen[k]].c, 'R %.6f' % Req, 'fans', np.round(qf, 3), 'Q %.3f' % Q)
    import bisect
    with open(out_csv, 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['point', 'flow_m3_s'])
        for r in P.points:
            t = r.get('time', '')
            k = bisect.bisect_left(times, t) - 1
            k = max(k, 0)
            qf, Q, qu = st_res[k]
            b = r.get('branch')
            if b in M.fidx:
                v = qf[M.fidx[b]]
            elif b in M.pidx:
                v = Q * qu[M.pidx[b]]
            else:
                v = float('nan')
            wr.writerow([r.get('point'), '%.4f' % v])


def rank_by_impact(M, sol, Rair, Rstop, Rdoor, must):
    """order the airways awaiting a survey by how much their uncertain resistance moves the
    airflow at the survey points"""
    P = M.P
    times = [t for t, _ in M.states]
    import bisect
    ks = sorted(set(max(bisect.bisect_left(times, r.get('time', '')) - 1, 0) for r in P.points))
    if len(ks) > 12:
        ks = [ks[i] for i in np.linspace(0, len(ks) - 1, 12).astype(int)]
    pts_by_k = {}
    for r in P.points:
        k = max(bisect.bisect_left(times, r.get('time', '')) - 1, 0)
        pts_by_k.setdefault(k, []).append(r.get('branch'))
    imp = {}
    for b in must:
        worst = 0.0
        for k in ks:
            Req, qu, w = sol[k]
            R = M.Rvec(Rair, Rstop, M.states[k][1], Rdoor)
            R2 = R.copy(); R2[M.pidx[b]] *= 1.25
            q2, Req2, _ = M.net.solve(R2)
            Q = 1.0
            for br in pts_by_k.get(k, []):
                if br in M.pidx:
                    i = M.pidx[br]
                    rel = abs(q2[i] - qu[i]) / max(abs(qu[i]), 0.03 / 250)
                    worst = max(worst, rel)
            worst = max(worst, 0.5 * abs(math.log(Req2 / Req)))
        imp[b] = worst
    dbg('impact', imp)
    return sorted(must, key=lambda b: -imp[b])


def place_order(pkg, order):
    cmd = ['pqsurvey', pkg] + list(order)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    except Exception as e:
        dbg('pqsurvey failed', e)
        return {}
    out = {}
    for line in res.stdout.splitlines():
        parts = [x.strip() for x in line.split(',')]
        if len(parts) >= 3 and parts[0] in order:
            dp = fnum(parts[1]); q = fnum(parts[2])
            if dp is not None and q is not None:
                out[parts[0]] = (dp, q)
    if res.returncode != 0:
        dbg('pqsurvey rc', res.returncode, res.stderr.strip(), res.stdout.strip())
    return out


def main():
    if len(sys.argv) != 3:
        print('usage: python3 airflow.py PACKAGE_DIR OUT_CSV', file=sys.stderr)
        sys.exit(2)
    try:
        run(sys.argv[1], sys.argv[2])
    except Exception:
        import traceback
        traceback.print_exc()
        # last resort: still give one row for every point
        if not os.path.exists(sys.argv[2]):
            rows = read_csv(os.path.join(sys.argv[1], 'points.csv'))
            with open(sys.argv[2], 'w', newline='') as f:
                wr = csv.writer(f); wr.writerow(['point', 'flow_m3_s'])
                for r in rows:
                    wr.writerow([r.get('point'), '0.0000'])
        sys.exit(1)


if __name__ == '__main__':
    main()
