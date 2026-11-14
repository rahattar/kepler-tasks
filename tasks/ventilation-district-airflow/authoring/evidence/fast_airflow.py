"""fast_airflow.py PACKAGE_DIR OUT_CSV: the second solution's method, written to run inside the limit.

naive_airflow.py with its two solvers replaced and nothing else changed: the records are read, the stoppings
judged, the order placed and the turn looked for exactly as there.

  - The district without its fans is solved by Newton's method on the node pressures, one sparse system a
    step, started from the pressures of the state before, once for every log entry. Its resistance seen from
    the fan house and every branch's share of the fans' air are kept, so looking for the turn replays the fans
    alone.
  - The fans are not integrated. They are carried by the rule VS-4 section 5 states: while a change is made
    every fan stays on the part of its characteristic it is on; where a change brings a fan to the peak from
    beyond it, or to the lowest point of the dip from below it, that fan crosses to its other falling part and
    every other fan stays where it was. A steady state of the fans is a root of their pressure balance, found by
    Newton's method on the part of each characteristic it is meant to be on, and it is kept only where it is
    stable: the balance's Jacobian is symmetric, so a state is stable for any inertia of the air exactly when
    the Jacobian is negative definite.
"""
import csv, json, os, subprocess, sys
import numpy as np

ACC = 0.003

def rows(folder, name):
    with open(os.path.join(folder, name), newline="") as f: return list(csv.DictReader(f))

def fan_pressure(curve, q):
    qs, ps = curve
    if q <= qs[0]: i = 0
    elif q >= qs[-1]: i = len(qs) - 2
    else:
        i = 0
        while qs[i + 1] < q: i += 1
    return ps[i] + (ps[i + 1] - ps[i]) * (q - qs[i]) / (qs[i + 1] - qs[i])

def stall_marks(curve):
    qs, ps = curve
    t = 1
    while not (ps[t] < ps[t - 1] and ps[t] <= ps[t + 1]): t += 1
    k = t
    while k < len(qs) - 1 and ps[k + 1] > ps[k]: k += 1
    return qs[t], qs[k]

import scipy.sparse as sp
from scipy.sparse.linalg import splu


class Passive:
    """The district without its fans, 0 Pa at ATM and -1 Pa at the fan house: every branch's flow by Newton's
    method on the free nodes' pressures, warm-started from the last solution."""

    def __init__(self, nnodes, ends, atm, fan_house):
        self.ends = ends; self.n = nnodes
        self.free = np.array([i for i in range(nnodes) if i not in (atm, fan_house)])
        pos = -np.ones(nnodes, int); pos[self.free] = np.arange(len(self.free))
        u = np.array([a for a, b in ends]); v = np.array([b for a, b in ends])
        self.u, self.v = u, v
        rows_, cols, vals = [], [], []
        for j in range(len(ends)):
            if pos[u[j]] >= 0: rows_.append(pos[u[j]]); cols.append(j); vals.append(1.0)
            if pos[v[j]] >= 0: rows_.append(pos[v[j]]); cols.append(j); vals.append(-1.0)
        self.Af = sp.csr_matrix((vals, (rows_, cols)), shape=(len(self.free), len(ends)))
        self.p = np.zeros(nnodes); self.p[fan_house] = -1.0
        self.fh = fan_house
        self.started = False

    def flows(self, R):
        p = self.p.copy()
        if not self.started:                                   # a first guess from the linear law
            G = sp.diags(1.0 / R)
            K = (self.Af @ G @ self.Af.T).tocsc()
            rhs = -(self.Af @ (G @ (p[self.u] - p[self.v])))
            p[self.free] = splu(K).solve(rhs)
            self.started = True
        for it in range(60):
            dp = p[self.u] - p[self.v]
            a = np.maximum(np.abs(dp), 1e-12)
            q = np.sign(dp) * np.sqrt(a / R)
            res = self.Af @ q                                  # outflow less inflow at every free node
            g = 0.5 / np.sqrt(R * a)
            K = (self.Af @ sp.diags(g) @ self.Af.T).tocsc()
            step = splu(K).solve(-res)
            scale = 1.0
            big = np.abs(step).max()
            if big > 0.5: scale = 0.5 / big                    # pressures here are fractions of 1 Pa
            p[self.free] += scale * step
            if scale == 1.0 and big < 1e-13: break
        self.p = p
        dp = p[self.u] - p[self.v]
        return np.sign(dp) * np.sqrt(np.abs(dp) / R)


def fan_pressure_slope(curve, q):
    qs, ps = curve
    i = int(np.clip(np.searchsorted(qs, q, side="right") - 1, 0, len(qs) - 2))
    s = (ps[i + 1] - ps[i]) / (qs[i + 1] - qs[i])
    return ps[i] + s * (q - qs[i]), s


def balance(curves, legs, r, q):
    total = q.sum()
    f = np.zeros(len(q)); d = np.zeros(len(q))
    for k, (c, l, x) in enumerate(zip(curves, legs, q)):
        P, s = fan_pressure_slope(c, x)
        f[k] = P - l * x * abs(x) - r * total * abs(total); d[k] = s - 2.0 * l * abs(x)
    J = np.diag(d) - 2.0 * r * abs(total) * np.ones((len(q), len(q)))
    return f, J


def fans_root(curves, legs, r, q0, want, marks):
    """A stable steady state of the fans with each on the part `want` gives it ("R" beyond the peak, "L" short
    of the dip's lowest point), from q0; None if there is none there."""
    lo = np.array([m[1] if w == "R" else c[0][0] for w, m, c in zip(want, marks, curves)])
    hi = np.array([c[0][-1] if w == "R" else m[0] for w, m, c in zip(want, marks, curves)])
    q = np.clip(np.array(q0, float), lo, hi)
    for it in range(100):
        f, J = balance(curves, legs, r, q)
        if np.abs(f).max() < 1e-9: break
        try: step = np.linalg.solve(J, -f)
        except np.linalg.LinAlgError: return None
        q = np.clip(q + step, lo, hi)
    else:
        return None
    f, J = balance(curves, legs, r, q)
    if np.abs(f).max() > 1e-6 or np.linalg.eigvalsh(J).max() >= 0.0: return None
    if any((x <= m[1]) if w == "R" else (x >= m[0]) for x, w, m in zip(q, want, marks)): return None
    return q


def main(folder, out):
    br = rows(folder, "branches.csv"); allowance = json.load(open(os.path.join(folder, "district.json")))["survey_allowance"]
    name = [r["branch"] for r in br]; at = {n: i for i, n in enumerate(name)}
    nodes = {}
    for r in br:
        for x in (r["from_node"], r["to_node"]): nodes.setdefault(x, len(nodes))
    # ---- resistances on record
    last = {}
    for r in rows(folder, "surveys.csv"):
        if r["branch"] not in last or r["date"] > last[r["branch"]][0]:
            last[r["branch"]] = (r["date"], float(r["dp_Pa"]), float(r["q_m3_s"]))
    stale = []
    for r in rows(folder, "work_log.csv"):
        if r["work"] in ("RESUPPORTED", "ENLARGED") and r["date"] > last[r["branch"]][0] and r["branch"] not in stale: stale.append(r["branch"])
    by_day = {}
    for r in rows(folder, "surveys.csv"): by_day.setdefault(r["date"], {})[r["branch"]] = (float(r["dp_Pa"]), float(r["q_m3_s"]))
    frm = {r["branch"]: r["from_node"] for r in br}; to = {r["branch"]: r["to_node"] for r in br}
    open_stoppings = {}
    for r in br:
        if r["kind"] != "stopping": continue
        seen = []
        for day, got in by_day.items():
            arriving = [v for b, v in got.items() if to[b] == r["from_node"]]; leaving = [v for b, v in got.items() if frm[b] == r["from_node"]]
            if len(arriving) != 1 or len(leaving) != 1: continue
            lost = arriving[0][1] - leaving[0][1]                       # air the next gate road does not carry on
            # pressure across the stopping: inbye along the intake, over the face, back along the return
            node, drop, guard = r["from_node"], 0.0, 0
            while node != r["to_node"] and guard < 10000:
                guard += 1
                onward = [b for b in got if frm[b] == node and b != ""]
                if not onward: drop = None; break
                b = onward[0]; drop += got[b][0]; node = to[b]
            if drop is None or node != r["to_node"]: continue
            seen.append((lost, drop, ACC * (abs(arriving[0][1]) + abs(leaving[0][1]))))
        if seen and all(lost > 5 * slack and lost > 4 * (max(drop, 0.0) / float(r["resistance_Ns2_m8"])) ** 0.5 for lost, drop, slack in seen):
            open_stoppings[r["branch"]] = sum(drop / lost ** 2 for lost, drop, slack in seen) / len(seen)
    fan_rows = rows(folder, "fans.csv")
    sheet = {}
    for r in rows(folder, "fan_curves.csv"):
        c = sheet.setdefault((r["model"], r["blade_setting"]), ([], [])); c[0].append(float(r["flow_m3_s"])); c[1].append(float(r["pressure_Pa"]))
    fan_branch = [at[r["branch"]] for r in fan_rows]
    curves = [sheet[(r["model"], r["blade_setting"])] for r in fan_rows]
    legs = [float(br[j]["resistance_Ns2_m8"]) for j in fan_branch]
    order = stale + [s for s in open_stoppings][:max(0, allowance - len(stale))]
    read_fan = None
    if len(order) < allowance:
        read_fan = int(np.argmax(legs)); order.append(name[fan_branch[read_fan]])
    readings = {}
    if order:
        reply = subprocess.run(["pqsurvey", folder] + order, capture_output=True, text=True)
        if reply.returncode != 0: raise SystemExit("survey order refused: " + reply.stdout.strip())
        for r in csv.DictReader(reply.stdout.splitlines()): readings[r["branch"]] = (float(r["dp_Pa"]), float(r["q_m3_s"]))
    R = np.zeros(len(br))
    for j, r in enumerate(br):
        n = r["branch"]
        if n in readings and r["kind"] in ("airway", "stopping"): R[j] = readings[n][0] / (readings[n][1] * abs(readings[n][1]))
        elif r["kind"] == "airway": R[j] = last[n][1] / (last[n][2] * abs(last[n][2]))
        elif r["kind"] == "stopping": R[j] = open_stoppings.get(n, float(r["resistance_Ns2_m8"]))
    reg = {(r["regulator"], r["setting"]): float(r["resistance_Ns2_m8"]) for r in rows(folder, "regulators.csv")}
    door = {r["door"]: {"closed": float(r["resistance_closed_Ns2_m8"]), "open": float(r["resistance_open_Ns2_m8"])} for r in rows(folder, "doors.csv")}
    where = {r["item"]: at[r["branch"]] for r in br if r["kind"] in ("regulator", "door")}
    def setting(item, s): return door[item][s] if item in door else reg[(item, s)]
    # ---- the passive district: every branch but the fans, between ATM and the fan house
    fan_house = nodes[br[fan_branch[0]]["from_node"]]
    passive = [j for j in range(len(br)) if j not in fan_branch]
    ends = [(nodes[br[j]["from_node"]], nodes[br[j]["to_node"]]) for j in passive]
    solver = Passive(len(nodes), ends, nodes["ATM"], fan_house)
    def seen_from_fans(R):
        q = solver.flows(R[passive])
        total = sum(q[k] for k, (u, v) in enumerate(ends) if v == fan_house) - sum(q[k] for k, (u, v) in enumerate(ends) if u == fan_house)
        return 1.0 / total ** 2, q / total                    # the district's resistance, and each branch's share of the fans' air
    log = rows(folder, "log.csv"); t0 = log[0]["time"]
    for r in log:
        if r["time"] == t0: R[where[r["item"]]] = setting(r["item"], r["setting"])
    points = rows(folder, "points.csv")
    rounds = sorted({r["time"] for r in points})
    marks = [stall_marks(c) for c in curves]
    def limb(i, q): return "L" if q <= marks[i][0] else ("R" if q >= marks[i][1] else "M")
    def limbs(q): return "".join(limb(k, x) for k, x in enumerate(q))

    def follow(q, r_from, r_to):
        """The fans through one gradual change of the district's resistance, by the rule of VS-4 section 5."""
        want = limbs(q)
        got = fans_root(curves, legs, r_to, q, want, marks)
        if got is not None: return got                         # the state lasts the whole change
        for s in range(1, 25):
            r = r_from * (r_to / r_from) ** (s / 24.0)
            got = fans_root(curves, legs, r, q, want, marks)
            crossings = 0
            while got is None:
                crossings += 1
                if crossings > len(q): raise SystemExit("no steady state of the fans")
                # the state ended in this step: the fan nearest the end of its part crosses to its other part
                ends_near = [((x - m[1]) / m[1]) if w == "R" else ((m[0] - x) / m[0]) for x, w, m in zip(q, want, marks)]
                k = int(np.argmin(ends_near))
                want = want[:k] + ("L" if want[k] == "R" else "R") + want[k + 1:]
                guess = q.copy(); guess[k] = 0.8 * marks[k][0] if want[k] == "L" else 1.05 * marks[k][1]
                got = fans_root(curves, legs, r, guess, want, marks)
            q = got
        return q

    states = {}
    def state(i, Rn):
        if i not in states: states[i] = seen_from_fans(Rn)
        return states[i]

    def carry(turn=None):
        """Through the record. turn = (index of a log row, factor): from that movement on the district's resistance
        is taken that much higher or lower, which is how a movement at the stall point is made to go the other way."""
        Rn = R.copy()
        r_now, share = state(-1, Rn)
        q = fans_root(curves, legs, r_now, [1.1 * m[1] for m in marks], "R" * len(curves), marks)   # VS-4: beyond the peak
        if q is None: raise SystemExit("no steady state with every fan beyond its peak as the record opens")
        flows = {}; large = []; scale = 1.0
        todo = sorted([(r["time"], 0, i) for i, r in enumerate(log) if r["time"] != t0] + [(t, 1, None) for t in rounds])
        for t, kind, i in todo:
            if kind == 1:
                full = np.zeros(len(br)); full[passive] = share * q.sum(); full[fan_branch] = q
                flows[t] = full; continue
            row = log[i]; j = where[row["item"]]; old = Rn[j]; Rn[j] = setting(row["item"], row["setting"])
            before = limbs(q)
            r_next, share = state(i, Rn)
            if turn and turn[0] == i: scale = turn[1]
            r_next *= scale
            q = follow(q, r_now, r_next)
            if max(Rn[j] / old, old / Rn[j]) > 3.0:
                # a large movement is a candidate for the turn if a fan changed limb at it, or a healthy fan was
                # left within 5 per cent of the quantity at its peak
                room = min([(x - marks[k][1]) / marks[k][1] for k, x in enumerate(q) if x >= marks[k][1]] or [0.0])
                if before != limbs(q) or room < 0.05: large.append(i)
            r_now = r_next
        return flows, q, large

    flows, q_end, large = carry()
    if read_fan is not None:
        q_read = readings[name[fan_branch[read_fan]]][1]
        if limb(read_fan, q_read) != limb(read_fan, q_end[read_fan]):
            # going back from the end, the first large movement that, with the district's resistance 1.2 per cent up
            # or down from there on, leaves the fan where it was read; then the least such change
            turned = None
            for i in reversed(large):
                for sign in (1.0, -1.0):
                    fl, qe, _ = carry((i, 1.0 + sign * 0.012))
                    if limb(read_fan, qe[read_fan]) != limb(read_fan, q_read): continue
                    lo, hi = 0.0, 0.012
                    for _ in range(6):
                        mid = 0.5 * (lo + hi); fl2, qe2, _ = carry((i, 1.0 + sign * mid))
                        if limb(read_fan, qe2[read_fan]) == limb(read_fan, q_read): hi = mid; fl = fl2
                        else: lo = mid
                    turned = fl; break
                if turned is not None: break
            if turned is not None: flows = turned
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["point", "flow_m3_s"])
        for r in points: w.writerow([r["point"], "%.4f" % flows[r["time"]][at[r["branch"]]]])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
