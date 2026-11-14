#!/usr/bin/env python3
"""HT-5 calculation of the oil quenching of round bars, for one site package.

    python3 quench.py PACKAGE_DIR OUT_CSV

1. The oil of every load (HT-5 section 5) is settled from the package's records:
   - the tanks that really share one charge of oil are found from the analyses on file (a tank whose
     figures do not follow the rest of its registered system is not fed by that system's reservoir);
   - the charges of each such oil unit are delimited by the CHARGE_RENEWED jobs of its system;
   - the one laboratory order of the package is spent on the units whose figures on the sampling date
     cannot be known from the records (renewed charges, tanks not on their registered system, charges
     ageing faster than a charge in service can), then on the rest by the size of the error avoided;
   - old charge: its latest analysis holds to the renewal; new charge: its analysis; charge not renewed:
     linear in time from its latest analysis on file to its analysis on the samples' date.
2. Every load is solved (HT-5 sections 2 to 4, 6, 7): radial conduction, vertex-centred finite volumes,
   Kirchhoff transform for k(T), enthalpy for c_p(T), linearly implicit variable-step BDF2 with local
   error control, all loads advanced together as one vectorised batch.
"""
import csv
import json
import os
import subprocess
import sys
import math
import re
import time

import numpy as np

DEBUG = bool(os.environ.get('QUENCH_DEBUG'))
OUT_COLS = ['load', 't85_core_s', 'cr700_core_K_s', 'dT_max_K', 'ts_core500_C', 't150_core_s']


def log(*a):
    if DEBUG:
        print(*a, file=sys.stderr)


# ----------------------------------------------------------------------------------------------------
# reading the package
# ----------------------------------------------------------------------------------------------------

def read_csv(path):
    try:
        with open(path, newline='', encoding='utf-8-sig') as fh:
            rows = list(csv.DictReader(fh))
    except Exception:
        return []
    out = []
    for r in rows:
        out.append({(k or '').strip(): (v or '').strip() if isinstance(v, str) else v for k, v in r.items()})
    return out


def day(s):
    s = str(s).strip()[:10]
    return int(np.datetime64(s, 'D').astype(np.int64))


def fnum(s, default=float('nan')):
    try:
        return float(s)
    except Exception:
        return default


ROUND = 182.6  # days in a six-monthly sample round


# ----------------------------------------------------------------------------------------------------
# the laboratory
# ----------------------------------------------------------------------------------------------------

def order_lab(pkg, tanks):
    if not tanks:
        return {}
    try:
        p = subprocess.run(['labsample', pkg] + list(tanks), capture_output=True, text=True, timeout=15)
    except Exception as e:
        log('lab failed', e)
        return {}
    log('lab rc', p.returncode, p.stdout.strip(), p.stderr.strip())
    res = {}
    want = set(tanks)
    for line in (p.stdout or '').splitlines():
        parts = [x.strip() for x in line.split(',')]
        if len(parts) < 4 or parts[0] not in want:
            continue
        v = [fnum(x) for x in parts[1:4]]
        if all(math.isfinite(x) for x in v) and v[0] > 0 and v[2] > 0 and v[1] > 40:
            res[parts[0]] = tuple(v)
    return res


# ----------------------------------------------------------------------------------------------------
# oil units and their figures (HT-5 section 5)
# ----------------------------------------------------------------------------------------------------

# One charge of oil analysed twice on one date agrees within the laboratory's repeatability (0.5 %),
# figures rounded to 0.1 K/s and 0.01 K/s; between rounds a charge in service rises by < 0.5 %.
SAME_RTOL = 0.0080      # same date (or interpolated between bracketing analyses)
NEAR_RTOL = 0.0080      # nearest analysis on one side only, plus ageing allowance per round
TC_TOL = 2.01           # T_CRmax, K


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-9)


def figs_close(a, b, slack_rounds=0.0, rtol=SAME_RTOL, ttol=TC_TOL):
    rt = rtol + 0.005 * slack_rounds
    tt = ttol + 1.0 * slack_rounds
    return rel(a[0], b[0]) <= rt and rel(a[2], b[2]) <= rt and abs(a[1] - b[1]) <= tt


def series_at(hist, d):
    """hist: sorted [(day, figs)]. Value at day d: (figs, days to the nearest analysis if not bracketed)."""
    lo = None
    hi = None
    for h in hist:
        if h[0] == d:
            return h[1], 0.0
        if h[0] < d:
            lo = h
        elif hi is None:
            hi = h
    if lo is not None and hi is not None:
        f = (d - lo[0]) / float(hi[0] - lo[0])
        return tuple(lo[1][k] + f * (hi[1][k] - lo[1][k]) for k in range(3)), 0.0
    near = lo if lo is not None else hi
    return near[1], float(abs(near[0] - d))


def compat(hA, hB, maxdist=400.0):
    """Can two analysed histories be one charge?  -> (number of comparisons, all agree).
    Analyses of the same date, or bracketed by the other's analyses, are compared closely; only when
    there are none of those are analyses compared with the other's nearest, allowing for ageing."""
    if not hA or not hB:
        return 0, True
    close, far = [], []
    for (h1, h2) in ((hA, hB), (hB, hA)):
        for (d, fa) in h1:
            v, dist = series_at(h2, d)
            if dist > maxdist:
                continue
            (close if dist == 0 else far).append((fa, v, dist))
    if close:
        return len(close), all(figs_close(a, b) for a, b, _ in close)
    return len(far), all(figs_close(a, b, slack_rounds=dist / ROUND, rtol=NEAR_RTOL) for a, b, dist in far)


def pooled(samples, tanks, lo=None, hi=None):
    """The charge's figures on each date: the mean of its analyses on that date."""
    acc = {}
    for t in tanks:
        for (d, f) in samples.get(t, []):
            if (lo is not None and d < lo) or (hi is not None and d >= hi):
                continue
            acc.setdefault(d, []).append(f)
    return [(d, tuple(np.mean(np.array(acc[d], float), axis=0))) for d in sorted(acc)]


class Unit:
    """Tanks taken to hold one oil (one reservoir)."""

    def __init__(self, uid, system, tanks, flag='register', reg=None):
        self.uid = uid
        self.system = system          # system whose CHARGE_RENEWED jobs apply to this oil
        self.reg = reg if reg is not None else system  # registered system of the tanks
        self.tanks = list(tanks)
        self.flag = flag              # register | ambiguous | outlier | split
        self.renewals = []
        self.hist = []
        self.lab = None
        self.lab_est = None
        self.extra_renewal = None
        self.sampled = []

    def __repr__(self):
        return '%s[%s sys=%s reg=%s %s]' % (self.uid, ','.join(self.tanks), self.system, self.reg, self.flag)


def largest_clique(n, ok):
    """Largest sets of mutually compatible members (indices). Returns list of the largest sets."""
    if n == 0:
        return [[]]
    if n <= 12:
        best = []
        for mask in range(1, 1 << n):
            idx = [i for i in range(n) if mask >> i & 1]
            if len(best) and len(idx) < len(best[0]):
                continue
            if all(ok[a][b] for ai, a in enumerate(idx) for b in idx[ai + 1:]):
                if not best or len(idx) > len(best[0]):
                    best = [idx]
                elif len(idx) == len(best[0]):
                    best.append(idx)
        return best
    cur = []
    for i in sorted(range(n), key=lambda i: -sum(ok[i])):
        if all(ok[i][j] for j in cur):
            cur.append(i)
    return [sorted(cur)]


def find_units(tanks, tank_sys, samples, renew):
    units = []
    outliers = []
    order_sys = []
    members_of = {}
    for t in tanks:
        s = tank_sys[t]
        if s not in members_of:
            members_of[s] = []
            order_sys.append(s)
        members_of[s].append(t)
    for s in order_sys:
        members = members_of[s]
        cuts = [None] + sorted(renew.get(s, [])) + [None]
        parts = [{m: pooled(samples, [m], cuts[i], cuts[i + 1]) for m in members} for i in range(len(cuts) - 1)]
        withh = [m for m in members if any(p[m] for p in parts)]
        without = [m for m in members if m not in withh]
        n = len(withh)
        ok = [[True] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                good = all(compat(p[withh[i]], p[withh[j]])[1] for p in parts)
                ok[i][j] = ok[j][i] = good
        cl = largest_clique(n, ok)
        if len(cl) == 1:
            core = [withh[i] for i in cl[0]] + without
            units.append(Unit('U%d' % len(units), s, core))
            outliers += [(m, s) for m in withh if m not in core]
        else:
            # no majority among the analysed tanks of the system: each one is a unit of its own
            log('system', s, 'has no consistent majority', withh)
            for i, m in enumerate(withh):
                units.append(Unit('U%d' % len(units), s, [m] + (without if i == 0 else []), flag='ambiguous'))
    for (m, s) in outliers:
        hm = pooled(samples, [m])
        cands = []
        for u in units:
            if u.reg == s or u.flag != 'register':
                continue
            nc, g = compat(hm, pooled(samples, u.tanks))
            if g and nc >= 4:
                cands.append(u)
        if len(cands) == 1:
            cands[0].tanks.append(m)
            log('tank', m, 'registered on', s, 'follows the oil of', cands[0])
            continue
        placed = False
        for u in units:
            if u.flag == 'outlier' and u.reg == s:
                nc, g = compat(hm, pooled(samples, u.tanks))
                if g and nc >= 2:
                    u.tanks.append(m)
                    placed = True
                    break
        if not placed:
            units.append(Unit('U%d' % len(units), None, [m], flag='outlier', reg=s))
            log('tank', m, 'registered on', s, 'does not hold that system\'s oil')
    for u in units:
        u.renewals = sorted(renew.get(u.system, [])) if u.system is not None else []
        u.hist = pooled(samples, u.tanks)
    return units


def aged_from(v, v0, rounds):
    """Is v what the charge analysed as v0 can have become by ageing over the given rounds?"""
    for c in (0, 2):
        r = v[c] / v0[c] - 1.0
        if r < -0.005 or r > 0.005 * rounds + 0.006:
            return False
    return abs(v[1] - v0[1]) <= 1.5 + 0.5 * rounds


def ageing(hist, dsamp):
    """Assess a charge's analyses: (abnormal, projected change to the samples' date in per cent,
    per-day slopes of the three figures)."""
    if len(hist) < 2:
        return False, 0.0, (0.0, 0.0, 0.0)
    ds = np.array([h[0] for h in hist], float)
    F = np.array([h[1] for h in hist], float)
    abnormal = False
    slopes = []
    for c in range(3):
        y = F[:, c]
        slopes.append(np.polyfit(ds, y, 1)[0] if np.ptp(ds) > 0 else 0.0)
    for c in (0, 2):
        y = F[:, c]
        for i in range(1, len(ds)):
            r = (ds[i] - ds[i - 1]) / ROUND
            ch = (y[i] - y[i - 1]) / y[i - 1]
            if ch > 0.005 * max(r, 1.0) + 0.005 or ch < -0.007:
                abnormal = True
        rs = slopes[c] * ROUND / max(np.mean(y), 1e-9)
        if rs > 0.006 or rs < -0.004:
            abnormal = True
    if np.ptp(F[:, 1]) > 2.01 or abs(slopes[1]) * ROUND > 0.75:
        abnormal = True
    span = max(dsamp - ds[-1], 0.0)
    drift = max(abs(slopes[0]) / np.mean(F[:, 0]), abs(slopes[2]) / np.mean(F[:, 2])) * span * 100.0
    drift += abs(slopes[1]) * span * 3.0
    return abnormal, drift, tuple(slopes)


def settle(pkg):
    site = {}
    try:
        with open(os.path.join(pkg, 'site.json'), encoding='utf-8') as fh:
            site = json.load(fh)
    except Exception:
        site = {}
    try:
        budget = max(int(float(site.get('lab_samples', 0))), 0)
    except Exception:
        budget = 0
    try:
        dsamp = day(site.get('samples_drawn'))
    except Exception:
        dsamp = None

    tank_rows = read_csv(os.path.join(pkg, 'tanks.csv'))
    sys_rows = read_csv(os.path.join(pkg, 'oil_systems.csv'))
    log_rows = read_csv(os.path.join(pkg, 'oil_log.csv'))
    smp_rows = read_csv(os.path.join(pkg, 'oil_samples.csv'))
    load_rows = read_csv(os.path.join(pkg, 'loads.csv'))

    tanks = []
    tank_sys = {}
    for r in tank_rows:
        t = r.get('tank', '')
        if t and t not in tank_sys:
            tanks.append(t)
            tank_sys[t] = r.get('oil_system', '') or ('OWN-' + t)
    systems = {r.get('oil_system', '') for r in sys_rows}
    registered = set(tanks)   # the package's quench tanks: the only ones the laboratory is asked for
    loads = []
    for r in load_rows:
        try:
            d = day(r.get('date'))
        except Exception:
            d = None
        loads.append(dict(load=r.get('load', ''), tank=r.get('tank', ''), day=d, steel=r.get('steel', ''),
                          D=fnum(r.get('diameter_mm')), Tf=fnum(r.get('furnace_C')), Tb=fnum(r.get('bath_C'))))
        t = r.get('tank', '')
        if t and t not in tank_sys:
            tanks.append(t)
            tank_sys[t] = 'OWN-' + t
    if dsamp is None:
        dl = [l['day'] for l in loads if l['day'] is not None]
        dsamp = (max(dl) + 1) if dl else 0

    renew = {}
    other_work = {}
    mentioned = set()
    tagset = set(tanks)
    for r in log_rows:
        try:
            d = day(r.get('date'))
        except Exception:
            continue
        s = r.get('oil_system', '')
        if s in tank_sys and s not in systems:   # job booked against a tank tag
            s = tank_sys[s]
        for tok in re.findall(r'[A-Za-z0-9][A-Za-z0-9_.-]*[A-Za-z0-9]', r.get('remarks', '') or ''):
            if tok in tagset:
                mentioned.add(tok)
        if (r.get('work', '') or '').strip().upper() != 'CHARGE_RENEWED':
            other_work.setdefault(s, []).append(d)
            continue
        renew.setdefault(s, []).append(d)
    for s in renew:
        renew[s] = sorted(set(renew[s]))

    acc = {}
    sys_members = {}
    for t in tanks:
        sys_members.setdefault(tank_sys[t], []).append(t)
    for r in smp_rows:
        t = r.get('sampled_at', '')
        try:
            d = day(r.get('date'))
        except Exception:
            continue
        v = (fnum(r.get('cr_max_K_s')), fnum(r.get('t_crmax_C')), fnum(r.get('cr_300_K_s')))
        if not all(math.isfinite(x) for x in v) or v[0] <= 0 or v[2] <= 0 or v[1] <= 40:
            continue
        if t not in tank_sys and t in sys_members:
            # drawn at a system rather than a tank: a pseudo-tank of that system
            tank_sys.setdefault('@' + t, t)
            if '@' + t not in tanks:
                tanks.append('@' + t)
            t = '@' + t
        acc.setdefault((t, d), []).append(v)
    samples = {}
    for (t, d), vs in acc.items():
        samples.setdefault(t, []).append((d, tuple(np.mean(np.array(vs), axis=0))))
    for t in samples:
        samples[t].sort()

    units = find_units(tanks, tank_sys, samples, renew)
    unit_of = {t: u for u in units for t in u.tanks}
    days_of = {}
    for l in loads:
        if l['day'] is not None:
            days_of.setdefault(l['tank'], []).append(l['day'])

    # what each unit still needs from the laboratory
    cands = []
    for u in units:
        lds = [d for t in u.tanks for d in days_of.get(t, [])]
        rl = [r for r in u.renewals if r <= dsamp]
        u.last_r = rl[-1] if rl else None
        u.cur = [h for h in u.hist if u.last_r is None or h[0] >= u.last_r]
        u.abnormal, u.drift, u.slopes = (False, 0.0, (0.0, 0.0, 0.0))
        if u.cur:
            dl = u.cur[-1][0]
            u.from_day = dl + 1
            u.abnormal, u.drift, u.slopes = ageing(u.cur, dsamp)
            if u.flag in ('outlier', 'ambiguous'):
                reg_ren = [r for r in renew.get(u.reg, []) if dl < r <= dsamp]
                if reg_ren or u.abnormal:
                    u.tier, u.risk = 1, max(6.0 if reg_ren else 1.0, u.drift)
                else:
                    u.tier, u.risk = 2, max(1.5, u.drift)
            elif u.abnormal:
                u.tier, u.risk = 1, max(1.0, u.drift)
            elif any(dl < w <= dsamp for w in other_work.get(u.system, [])):
                u.tier, u.risk = 2, max(1.0, u.drift)
            else:
                # T_CRmax weighs most (about 3 per cent of cr700 per K): an unsteady or fractional
                # T_CRmax makes the estimate of the laboratory's integer figure less sure
                tcs = [h[1][1] for h in u.cur]
                tc_risk = (max(tcs) - min(tcs)) + 2.0 * abs(tcs[-1] - round(tcs[-1]))
                u.tier, u.risk = 3, u.drift + 0.1 + tc_risk
        else:
            u.from_day = u.last_r if u.last_r is not None else -10 ** 9
            u.tier, u.risk = 0, 8.0
        u.need = sum(1 for d in lds if d >= u.from_day)
        u.score = u.risk * u.need
        log(u, 'tier', u.tier, 'risk %.2f' % u.risk, 'loads needing it', u.need,
            'abnormal' if u.abnormal else '')
        if u.need > 0 and any(t in registered for t in u.tanks):
            cands.append(u)

    def loads_from(t, d0):
        return sum(1 for d in days_of.get(t, []) if d >= d0)

    def tank_order(u):
        real = [t for t in u.tanks if t in registered]
        return sorted(real, key=lambda t: (-loads_from(t, u.from_day), tanks.index(t)))

    first = sorted([u for u in cands if u.tier <= 1], key=lambda u: -u.score)
    first += sorted([u for u in cands if u.tier == 2], key=lambda u: -u.score)
    first += sorted([u for u in cands if u.tier == 3], key=lambda u: -u.score)
    order = []
    for u in first:
        if len(order) >= budget:
            break
        to = tank_order(u)
        if to:
            order.append((to[0], u))
    if len(order) < budget:
        # spare samples: further tanks of the units sampled, as a check on the connections
        extra = []
        for u in first:
            if not any(uu is u for _, uu in order):
                continue
            for t in tank_order(u)[1:]:
                pri = -1 if t in mentioned else (u.tier if u.tier > 1 else 0)
                extra.append((pri, -loads_from(t, u.from_day), t, u))
        extra.sort(key=lambda e: (e[0], e[1]))
        for e in extra[:budget - len(order)]:
            order.append((e[2], e[3]))
    log('laboratory order:', [t for t, _ in order])
    labres = order_lab(pkg, [t for t, _ in order]) if order else {}

    # attach the analyses; a unit whose sampled tanks disagree is split
    out_units = []
    for u in units:
        got = [(t, labres[t]) for t, uu in order if uu is u and t in labres]
        if not got:
            out_units.append(u)
            continue
        groups = []
        for t, v in got:
            for g in groups:
                if figs_close(v, g[0][1]):
                    g.append((t, v))
                    break
            else:
                groups.append([(t, v)])
        groups.sort(key=lambda g: -len(g))
        sampled = {t for t, _ in got}
        for gi, g in enumerate(groups):
            if gi == 0:
                nu = u
                nu.tanks = [t for t in u.tanks if t not in sampled] + [t for t, _ in g]
            else:
                nu = Unit(u.uid + '/%d' % gi, u.system, [t for t, _ in g], flag='split', reg=u.reg)
                for a in ('renewals', 'hist', 'cur', 'last_r', 'abnormal', 'drift', 'slopes', 'from_day'):
                    setattr(nu, a, getattr(u, a))
                log('tanks', nu.tanks, 'do not hold the same oil as the rest of', u)
            nu.lab = tuple(np.mean(np.array([v for _, v in g]), axis=0))
            nu.sampled = [t for t, _ in g]
            out_units.append(nu)
    units = out_units

    # tanks off their registered system: renewed with it after all?  And tanks of a renewed system
    # whose oil on the samples' date is their old charge aged: not renewed with it.
    sys_lab = {}
    for u in units:
        if u.flag == 'register' and u.lab is not None and u.system is not None:
            sys_lab.setdefault(u.system, []).append(u.lab)
    for u in units:
        if u.lab is None:
            continue
        if u.flag == 'outlier' and u.cur:
            dl, vl = u.cur[-1]
            reg_ren = [r for r in renew.get(u.reg, []) if dl < r <= dsamp]
            if not reg_ren:
                continue
            same = any(figs_close(u.lab, v) for v in sys_lab.get(u.reg, []))
            if u.abnormal:
                est = tuple(vl[k] + u.slopes[k] * (dsamp - dl) for k in range(3))
                aged = figs_close(u.lab, est, rtol=0.02, ttol=3.0)
            else:
                aged = aged_from(u.lab, vl, (dsamp - dl) / ROUND)
            if same or not aged:
                u.extra_renewal = reg_ren[-1]
                log(u, 'taken as renewed with', u.reg)
        elif u.flag in ('ambiguous', 'split') and u.last_r is not None:
            before = [h for h in u.hist if h[0] < u.last_r]
            if not before:
                continue
            dl, vl = before[-1]
            same = any(figs_close(u.lab, v) for v in sys_lab.get(u.system, []))
            if not same and aged_from(u.lab, vl, (dsamp - dl) / ROUND):
                u.renewals = [r for r in u.renewals if r <= dl]
                rl = [r for r in u.renewals if r <= dsamp]
                u.last_r = rl[-1] if rl else None
                u.cur = [h for h in u.hist if u.last_r is None or h[0] >= u.last_r]
                log(u, 'taken as not renewed after', dl)
    # figures on the samples' date for units not sampled
    for u in units:
        if u.lab is None and u.cur:
            dl, vl = u.cur[-1]
            if u.abnormal:
                span = dsamp - dl
                u.lab_est = tuple(vl[k] + u.slopes[k] * span for k in range(3))
            else:
                u.lab_est = vl
        log(u, 'lab', u.lab, 'estimate', u.lab_est, 'extra renewal', u.extra_renewal)
    unit_of = {t: u for u in units for t in u.tanks}

    figs = np.zeros((len(loads), 3))
    for i, l in enumerate(loads):
        u = unit_of.get(l['tank'])
        v = figures_on(u, l['day'], dsamp) if (u is not None and l['day'] is not None) else None
        if v is None:
            allv = [h[1] for uu in units for h in uu.hist[-1:]]
            v = tuple(np.mean(np.array(allv), axis=0)) if allv else (75.0, 575.0, 6.6)
        figs[i] = v
    return loads, figs, units


def figures_on(u, d, dsamp):
    ren = [r for r in u.renewals if r <= dsamp]
    if u.extra_renewal is not None:
        ren = sorted(set(ren + [u.extra_renewal]))
    lo, hi = None, None
    for r in ren:
        if d >= r:
            lo = r
        elif hi is None:
            hi = r
    hist = [h for h in u.hist if (lo is None or h[0] >= lo) and (hi is None or h[0] < hi)]
    end = u.lab if u.lab is not None else u.lab_est
    if hi is None:   # the charge in the tank on the samples' date
        if hist:
            dl, vl = hist[-1]
            if d >= dl:
                if end is None:
                    return vl
                f = min(max((d - dl) / float(dsamp - dl), 0.0), 1.0) if dsamp > dl else 1.0
                return tuple(vl[k] + f * (end[k] - vl[k]) for k in range(3))
            return interp_hist(hist, d)
        if u.lab is not None:
            return u.lab
        prev = [h for h in u.hist if lo is None or h[0] < lo]
        return prev[-1][1] if prev else None
    # an old charge: its latest analysis holds to the renewal
    if hist:
        return hist[-1][1] if d >= hist[-1][0] else interp_hist(hist, d)
    later = [h for h in u.hist if h[0] >= hi]
    if later:
        return later[0][1]
    if u.lab is not None:
        return u.lab
    prev = [h for h in u.hist if h[0] < hi]
    return prev[-1][1] if prev else None


def interp_hist(hist, d):
    if d <= hist[0][0]:
        return hist[0][1]
    for i in range(1, len(hist)):
        if d <= hist[i][0]:
            a, b = hist[i - 1], hist[i]
            f = (d - a[0]) / float(b[0] - a[0])
            return tuple(a[1][k] + f * (b[1][k] - a[1][k]) for k in range(3))
    return hist[-1][1]


# ----------------------------------------------------------------------------------------------------
# HT-5 solver
# ----------------------------------------------------------------------------------------------------

RHO = 7800.0
KTAB = {'C45': ([20, 300, 600, 800, 900], [50, 44, 34, 26, 26]),
        '42CrMo4': ([20, 300, 600, 800, 900], [43, 40, 33, 27, 27])}
CTAB = {'C45': ([20, 300, 600, 720, 800, 900], [470, 560, 750, 900, 650, 650]),
        '42CrMo4': ([20, 300, 600, 720, 800, 900], [460, 550, 720, 850, 640, 640])}
KPROBE = 14200.0
TW = 1100
STEELS = ('C45', '42CrMo4')
LEVELS = np.array([800.0, 725.0, 675.0, 500.0, 150.0, -1e9])


def build_tables(steels):
    n = len(steels)
    cp = np.zeros((n, TW + 1)); kk = np.zeros((n, TW + 1))
    for i, s in enumerate(steels):
        cx, cy = CTAB[s]
        kx, ky = KTAB[s]
        cp[i] = np.interp(np.arange(TW + 1.0), cx, cy) * RHO
        kk[i] = np.interp(np.arange(TW + 1.0), kx, ky)
    dcp = np.diff(cp, axis=1)
    dk = np.diff(kk, axis=1)
    cp = cp[:, :-1]; kk = kk[:, :-1]
    Hc = np.concatenate([np.zeros((n, 1)), np.cumsum(cp + 0.5 * dcp, axis=1)[:, :-1]], axis=1)
    Pc = np.concatenate([np.zeros((n, 1)), np.cumsum(kk + 0.5 * dk, axis=1)[:, :-1]], axis=1)
    return [a.reshape(-1).copy() for a in (cp, dcp, Hc, kk, dk, Pc)]


def hcurve(Ts, h3, hp, tcr):
    lo = 0.6 * h3 + np.clip(Ts - 100.0, 0.0, 200.0) * (0.4 * h3 / 200.0)
    mid = h3 + np.clip(Ts - 300.0, 0.0, None) * ((hp - h3) / (tcr - 300.0))
    hi = hp - np.clip(Ts - tcr, 0.0, 120.0) * (0.85 * hp / 120.0)
    return np.where(Ts <= 300.0, lo, np.where(Ts <= tcr, mid, hi))


def solve_batch(steel_idx, D_mm, Tf, Tb, crmax, tcr, cr300, N=48, tol=0.01, rej=2.0, dt0=1e-3,
                maxsteps=60000, gmax=1.5, compact_frac=0.85, t_budget=None):
    M = len(D_mm)
    steel_idx = np.asarray(steel_idx, dtype=np.int64)
    R = np.asarray(D_mm, float) / 2000.0
    Tf = np.asarray(Tf, float)
    Tb = np.asarray(Tb, float)
    crmax = np.asarray(crmax, float); tcr = np.asarray(tcr, float); cr300 = np.asarray(cr300, float)
    hp = KPROBE * crmax / (tcr - 40.0)
    h3 = KPROBE * cr300 / 260.0
    cpT, dcpT, HcT, kT, dkT, PcT = build_tables(STEELS)
    x = np.linspace(0.0, 1.0, N + 1)
    xf = np.concatenate([[0.0], 0.5 * (x[1:] + x[:-1]), [1.0]])
    Vx = 0.5 * (xf[1:] ** 2 - xf[:-1] ** 2)
    Gc = (xf[1:-1] / np.diff(x))[:, None]

    def enth(TT, b):
        j = TT.astype(np.int64)
        f = TT - j
        idx = j + b
        return HcT[idx] + f * (cpT[idx] + 0.5 * f * dcpT[idx])

    tcross = np.full((5, M), np.nan)
    ts500 = np.full(M, np.nan)
    dTmax_g = np.zeros(M)
    act = np.arange(M)
    S = {}
    S['base'] = (steel_idx * TW)[None, :]
    S['V'] = Vx[:, None] * (R ** 2)[None, :]
    S['T'] = np.repeat(Tf[None, :], N + 1, axis=0)
    S['Tp'] = S['T'].copy()
    S['Hn'] = enth(S['T'], S['base']) * S['V']
    S['Hp'] = S['Hn'].copy()
    for k_, v_ in dict(t=np.zeros(M), tpv=np.zeros(M), dt=np.full(M, dt0), dtp=np.full(M, dt0),
                       first=np.ones(M, bool), R=R, Tb=Tb, h3=h3, hp=hp, tcr=tcr,
                       dT1=np.zeros(M), dT0=np.zeros(M), lvl=np.zeros(M, np.int64), dTmax=np.zeros(M)).items():
        S[k_] = v_
    nstep = 0
    nlast = M
    clock0 = time.time()
    relaxed = False
    while act.size and nstep < maxsteps:
        nstep += 1
        if t_budget is not None and not relaxed and nstep % 50 == 0:
            # keep within the time allowed: coarser steps if the run would not finish in time
            el = time.time() - clock0
            if el > 0.5 * t_budget or (nstep >= 200 and el / nstep * 1400 > t_budget):
                tol *= 3.0
                relaxed = True
                log('time guard: steps coarsened at step', nstep)
        T = S['T']; Tp = S['Tp']; dt = S['dt']; dtp = S['dtp']; first = S['first']; V = S['V']
        w = np.where(first, 0.0, dt / dtp)
        a0 = (1 + 2 * w) / (1 + w)
        a1 = -(1 + w)
        a2 = w * w / (1 + w)
        Tx = T + w * (T - Tp)
        np.clip(Tx, 1.0, TW - 2.0, out=Tx)
        j = Tx.astype(np.int64)
        f = Tx - j
        idx = j + S['base']
        cp = cpT[idx]; dcp = dcpT[idx]
        k = kT[idx]; dk = dkT[idx]
        H = (HcT[idx] + f * (cp + 0.5 * f * dcp)) * V
        P = PcT[idx] + f * (k + 0.5 * f * dk)
        cp += f * dcp
        k += f * dk
        Ts = Tx[-1]
        hs = hcurve(Ts, S['h3'], S['hp'], S['tcr'])
        flux = dt * Gc * (P[1:] - P[:-1])
        rhs = -(a0 * H + a1 * S['Hn'] + a2 * S['Hp'])
        rhs[:-1] += flux
        rhs[1:] -= flux
        Rh = dt * S['R'] * hs
        rhs[-1] -= Rh * (Ts - S['Tb'])
        gd = dt * Gc
        glo = gd * k[:-1]
        ghi = gd * k[1:]
        diag = (a0 * cp) * V
        diag[:-1] += glo
        diag[1:] += ghi
        diag[-1] += Rh
        np.negative(glo, out=glo)
        np.negative(ghi, out=ghi)
        d = thomas(glo, diag, ghi, rhs)
        Tn = Tx + d
        err = np.abs(d).max(axis=0)
        err[first] = 0.0
        acc = err <= rej * tol
        fac = np.sqrt(tol / np.maximum(err, 1e-300))
        np.clip(fac, 0.2, gmax, out=fac)
        rj = np.nonzero(~acc)[0]
        if rj.size:
            Tn[:, rj] = T[:, rj]
        t0 = S['tpv']; t1 = S['t']; t2 = t1 + dt
        lv = S['lvl']
        Tc2 = Tn[0]
        for _ in range(5):
            L = LEVELS[lv]
            hit = Tc2 <= L
            if not hit.any():
                break
            hi_ = np.nonzero(hit)[0]
            tc = quad_cross(t0[hi_], t1[hi_], t2[hi_], Tp[0, hi_], T[0, hi_], Tc2[hi_], L[hi_], first[hi_])
            tcross[lv[hi_], act[hi_]] = tc
            is5 = lv[hi_] == 3
            if is5.any():
                hh = hi_[is5]
                ts500[act[hh]] = quad_eval(t0[hh], t1[hh], t2[hh], Tp[-1, hh], T[-1, hh], Tn[-1, hh],
                                           tc[is5], first[hh])
            lv[hi_] += 1
        dTn = Tn[0] - Tn[-1]
        dT1 = S['dT1']; dT0 = S['dT0']
        ismax = acc & (dT1 >= dTn) & (dT1 >= dT0) & (~first)
        if ismax.any():
            im = np.nonzero(ismax)[0]
            pm = parab_max(t0[im], t1[im], t2[im], dT0[im], dT1[im], dTn[im])
            S['dTmax'][im] = np.maximum(S['dTmax'][im], pm)
        np.maximum(S['dTmax'], dTn, out=S['dTmax'])
        Hnew = enth(Tn, S['base']) * V
        newTp = T
        newHp = S['Hn']
        if rj.size:
            sTp = Tp[:, rj]; sHp = S['Hp'][:, rj]
            newTp[:, rj] = sTp
            newHp[:, rj] = sHp
        S['Tp'] = newTp; S['T'] = Tn
        S['Hp'] = newHp; S['Hn'] = Hnew
        S['dT0'] = np.where(acc, dT1, dT0)
        S['dT1'] = np.where(acc, dTn, dT1)
        S['tpv'] = np.where(acc, t1, t0)
        S['t'] = np.where(acc, t2, t1)
        S['dtp'] = np.where(acc, dt, dtp)
        S['first'] = first & ~acc
        S['dt'] = dt * fac
        done = lv >= 5
        nd = int(done.sum())
        if nd and (act.size - nd <= compact_frac * nlast or nd == act.size):
            keep = ~done
            dTmax_g[act[done]] = S['dTmax'][done]
            for kname in list(S.keys()):
                v = S[kname]
                S[kname] = v[:, keep] if v.ndim == 2 else v[keep]
            act = act[keep]
            nlast = act.size
    if act.size:
        dTmax_g[act] = S['dTmax']
    with np.errstate(all='ignore'):
        res = dict(t85_core_s=tcross[3] - tcross[0], cr700_core_K_s=50.0 / (tcross[2] - tcross[1]),
                   dT_max_K=dTmax_g, ts_core500_C=ts500, t150_core_s=tcross[4])
    return res, nstep


def parab_max(t0, t1, t2, y0, y1, y2):
    h1 = t1 - t0; h2 = t2 - t1
    with np.errstate(all='ignore'):
        d01 = (y1 - y0) / h1
        d12 = (y2 - y1) / h2
        c = (d12 - d01) / (h1 + h2)
        ts = 0.5 * (t1 + t2) - d12 / (2 * c)
        ts = np.clip(ts, t0, t2)
        p = y1 + d12 * (ts - t1) + c * (ts - t1) * (ts - t2)
    ok = np.isfinite(p) & (c < 0)
    return np.where(ok, np.maximum(p, y1), y1)


def quad_cross(t0, t1, t2, y0, y1, y2, L, first):
    with np.errstate(all='ignore'):
        tl = t1 + (L - y1) * (t2 - t1) / (y2 - y1)
        h1 = t1 - t0
        h2 = t2 - t1
        d01 = (y1 - y0) / h1
        d12 = (y2 - y1) / h2
        d012 = (d12 - d01) / (h1 + h2)
        tt = tl.copy()
        for _ in range(4):
            p = y1 + d12 * (tt - t1) + d012 * (tt - t1) * (tt - t2)
            dp = d12 + d012 * (2 * tt - t1 - t2)
            tt = tt - (p - L) / dp
    ok = np.isfinite(tt) & (tt >= t1) & (tt <= t2) & (~first) & (y1 > L)
    out = np.where(ok, tt, tl)
    return np.where(np.isfinite(out), out, t2)


def quad_eval(t0, t1, t2, y0, y1, y2, tt, first):
    h1 = t1 - t0
    h2 = t2 - t1
    with np.errstate(all='ignore'):
        d01 = (y1 - y0) / h1
        d12 = (y2 - y1) / h2
        d012 = (d12 - d01) / (h1 + h2)
        p = y1 + d12 * (tt - t1) + d012 * (tt - t1) * (tt - t2)
        lin = y1 + (y2 - y1) * (tt - t1) / h2
    out = np.where(np.isfinite(p) & ~first, p, lin)
    return np.where(np.isfinite(out), out, y2)


def thomas(lo, di, up, b):
    n = di.shape[0]
    c = np.empty_like(up)
    for i in range(1, n):
        np.divide(up[i - 1], di[i - 1], out=c[i - 1])
        di[i] -= lo[i - 1] * c[i - 1]
        b[i] -= lo[i - 1] * (b[i - 1] / di[i - 1])
    x = b
    x[-1] /= di[-1]
    for i in range(n - 2, -1, -1):
        x[i] = b[i] / di[i] - c[i] * x[i + 1]
    return x


# ----------------------------------------------------------------------------------------------------

def fmt(v, nd):
    if v is None or not np.isfinite(v):
        return '0'
    return ('%.' + str(nd) + 'f') % v


T_START = time.time()


def main():
    if len(sys.argv) < 3:
        print('usage: quench.py PACKAGE_DIR OUT_CSV', file=sys.stderr)
        sys.exit(0)
    pkg, out = sys.argv[1], sys.argv[2]
    loads, figs, units = [], None, []
    try:
        loads, figs, units = settle(pkg)
    except Exception as e:  # never leave without results
        log('settle failed', repr(e))
        if DEBUG:
            import traceback
            traceback.print_exc()
        rows = read_csv(os.path.join(pkg, 'loads.csv'))
        loads = [dict(load=r.get('load', ''), tank=r.get('tank', ''), day=None, steel=r.get('steel', ''),
                      D=fnum(r.get('diameter_mm')), Tf=fnum(r.get('furnace_C')), Tb=fnum(r.get('bath_C')))
                 for r in rows]
        figs = np.tile([75.0, 575.0, 6.6], (len(loads), 1))
    M = len(loads)
    res = None
    if M:
        st = np.array([1 if l['steel'].strip().lower() == '42crmo4' else 0 for l in loads])
        D = np.array([l['D'] if np.isfinite(l['D']) else 50.0 for l in loads])
        Tf = np.array([l['Tf'] if np.isfinite(l['Tf']) else 860.0 for l in loads])
        Tb = np.array([l['Tb'] if np.isfinite(l['Tb']) else 60.0 for l in loads])
        D = np.clip(D, 1.0, 1000.0)
        Tf = np.clip(Tf, 150.0, 1090.0)
        Tb = np.clip(Tb, 0.0, 149.0)
        try:
            res, nstep = solve_batch(st, D, Tf, Tb, figs[:, 0], figs[:, 1], figs[:, 2],
                                     t_budget=max(38.0 - (time.time() - T_START), 5.0))
            log('steps', nstep)
        except Exception as e:
            log('solver failed', repr(e))
            if DEBUG:
                import traceback
                traceback.print_exc()
            res = None
    try:
        with open(out, 'w', newline='') as fh:
            fh.write(','.join(OUT_COLS) + '\n')
            for i, l in enumerate(loads):
                if res is None:
                    vals = ['0'] * 5
                else:
                    vals = [fmt(res['t85_core_s'][i], 4), fmt(res['cr700_core_K_s'][i], 5),
                            fmt(res['dT_max_K'][i], 3), fmt(res['ts_core500_C'][i], 3),
                            fmt(res['t150_core_s'][i], 3)]
                fh.write(','.join([l['load']] + vals) + '\n')
    except Exception as e:
        print('cannot write %s: %r' % (out, e), file=sys.stderr)


if __name__ == '__main__':
    main()
    sys.exit(0)
