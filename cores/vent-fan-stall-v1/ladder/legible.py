"""ref_airflow.py PACKAGE_DIR OUT_CSV: airflow at every survey point of a district package, to VS-4 (bare core v1).

1. Every airway's resistance from its latest survey on file; airways worked on since have none and go on the
   order.
2. Every campaign's quantities are balanced at the two ends of every stopping. A stopping that passes far more
   air than the resistance it was built to allows is not that stopping any more: it goes on the order.
3. What is left of the allowance is spent on a fan: the district's present state, read and not calculated.
4. The state is carried through the log (v0's method). Where the fan as read is not on the limb the
   calculation ends on, the last large change whose outcome turns within the accuracy of the surveys is turned,
   and the record is carried on from there.
"""
import csv, json, os, subprocess, sys
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

MODE = "legible"
ACC = 0.003                     # a survey's pressure difference and quantity are each within 0.3 per cent
ALTERS = ("RESUPPORTED", "ENLARGED")

def read(folder, name):
    with open(os.path.join(folder, name), newline="") as f: return list(csv.DictReader(f))

class District:
    def __init__(self, folder):
        self.folder = folder
        self.allowance = json.load(open(os.path.join(folder, "district.json")))["survey_allowance"]
        br = self.br = read(folder, "branches.csv")
        self.names = [r["branch"] for r in br]; self.B = B = len(br)
        nodes = self.nodes = {"ATM": -1}
        for r in br:
            for x in (r["from_node"], r["to_node"]):
                if x not in nodes: nodes[x] = len(nodes) - 1
        self.N = N = len(nodes) - 1
        rows, cols, vals = [], [], []
        for j, r in enumerate(br):
            a, b = nodes[r["from_node"]], nodes[r["to_node"]]
            if a >= 0: rows.append(a); cols.append(j); vals.append(1.0)
            if b >= 0: rows.append(b); cols.append(j); vals.append(-1.0)
        self.A = sp.csr_matrix((vals, (rows, cols)), shape=(N, B)); self.At = self.A.T.tocsr()
        self.idx = idx = {n: j for j, n in enumerate(self.names)}
        self.item_branch = {r["item"]: j for j, r in enumerate(br) if r["kind"] in ("regulator", "door")}
        self.reg = {(r["regulator"], int(r["setting"])): float(r["resistance_Ns2_m8"]) for r in read(folder, "regulators.csv")}
        self.door = {r["door"]: (float(r["resistance_closed_Ns2_m8"]), float(r["resistance_open_Ns2_m8"])) for r in read(folder, "doors.csv")}
        curves = {}
        for r in read(folder, "fan_curves.csv"):
            c = curves.setdefault((r["model"], r["blade_setting"]), ([], [])); c[0].append(float(r["flow_m3_s"])); c[1].append(float(r["pressure_Pa"]))
        self.fans = []
        for r in read(folder, "fans.csv"):
            qs, ps = (np.array(v) for v in curves[(r["model"], r["blade_setting"])])
            k = 1
            while k < len(qs) - 1 and not (ps[k] < ps[k - 1] and ps[k] <= ps[k + 1]): k += 1
            kt = k
            while k < len(qs) - 1 and ps[k + 1] > ps[k]: k += 1
            self.fans.append((idx[r["branch"]], qs, ps, qs[kt], qs[k]))
        log = read(folder, "log.csv"); self.t0 = log[0]["time"]
        self.opening = [(r["item"], r["setting"]) for r in log if r["time"] == self.t0]
        self.events = [(r["time"], r["item"], r["setting"]) for r in log if r["time"] != self.t0]
        self.points = [(r["point"], r["time"], idx[r["branch"]]) for r in read(folder, "points.csv")]
        self.surveys = [(r["date"], r["branch"], float(r["dp_Pa"]), float(r["q_m3_s"])) for r in read(folder, "surveys.csv")]
        self.work = [(r["date"], r["branch"], r["work"]) for r in read(folder, "work_log.csv")]
        K = sp.bmat([[sp.identity(B), -self.At], [self.A, None]], format="csc"); K.sort_indices(); self.K = K
        self.diag = np.array([K.indptr[j] + int(np.searchsorted(K.indices[K.indptr[j]:K.indptr[j + 1]], j)) for j in range(B)])

    # ---- the records ----
    def on_file(self):
        latest = {}
        for day, nm, dp, q in self.surveys:
            if nm not in latest or day > latest[nm][0]: latest[nm] = (day, dp / (q * abs(q)))
        altered = sorted({nm for day, nm, kd in self.work if kd in ALTERS and nm in latest and day > latest[nm][0]})
        return latest, altered

    def breached(self):
        """Stoppings whose two ends miss balance, in every campaign, by far more than the stopping as built would pass."""
        frm = {r["branch"]: r["from_node"] for r in self.br}; to = {r["branch"]: r["to_node"] for r in self.br}
        days = {}
        for day, nm, dp, q in self.surveys: days.setdefault(day, {})[nm] = (dp, q)
        found = {}
        for r in self.br:
            if r["kind"] != "stopping": continue
            a, b = r["from_node"], r["to_node"]; est = []
            for day, rows in days.items():
                at_a = [(nm, v) for nm, v in rows.items() if a in (frm[nm], to[nm])]
                at_b = [(nm, v) for nm, v in rows.items() if b in (frm[nm], to[nm])]
                if len(at_a) < 2 or len(at_b) < 2: continue
                la = sum(v[1] if to[nm] == a else -v[1] for nm, v in at_a)          # air arriving at a and not leaving by an airway
                lb = sum(v[1] if frm[nm] == b else -v[1] for nm, v in at_b)         # air leaving b that did not arrive by an airway
                noise = ACC * (sum(abs(v[1]) for nm, v in at_a) + sum(abs(v[1]) for nm, v in at_b))
                # pressure across the stopping: round by the airways, from a inbye over the face and back to b
                dp = self.across(rows, frm, to, a, b)
                est.append((0.5 * (la + lb), noise, dp))
            if est and all(l > 4 * n + 3 * np.sqrt(max(dp, 0.0) / float(r["resistance_Ns2_m8"])) for l, n, dp in est):
                found[r["branch"]] = float(np.mean([dp / l ** 2 for l, n, dp in est]))
        return found

    def across(self, rows, frm, to, a, b):
        """p_a - p_b along surveyed airways of the same day (a walk over the airways, pressure differences summed)."""
        adj = {}
        for nm, (dp, q) in rows.items():
            adj.setdefault(frm[nm], []).append((to[nm], dp)); adj.setdefault(to[nm], []).append((frm[nm], -dp))
        seen = {a: 0.0}; todo = [a]
        for u in todo:
            for v, dp in adj.get(u, []):
                if v not in seen: seen[v] = seen[u] + dp; todo.append(v)        # seen[v] = p_a - p_v
        return seen.get(b, 0.0)

    def survey(self, branches):
        if not branches: return {}
        out = subprocess.run(["pqsurvey", self.folder] + list(branches), capture_output=True, text=True)
        if out.returncode != 0: raise RuntimeError("survey order refused: " + out.stdout.strip())
        return {r["branch"]: (float(r["dp_Pa"]), float(r["q_m3_s"])) for r in csv.DictReader(out.stdout.splitlines())}

    # ---- the network ----
    def res(self, item, setting):
        if item in self.door: return self.door[item][0 if setting == "closed" else 1]
        return self.reg[(item, int(setting))]

    def law(self, q, R):
        h = R * q * np.abs(q); d = 2.0 * R * np.abs(q)
        for j, qs, ps, qt, qp in self.fans:
            i = int(np.clip(np.searchsorted(qs, q[j], side="right") - 1, 0, len(qs) - 2))
            s = (ps[i + 1] - ps[i]) / (qs[i + 1] - qs[i])
            h[j] -= ps[i] + s * (q[j] - qs[i]); d[j] -= s
        return h, d

    def limbs(self, q):
        return "".join("L" if q[j] <= qt else ("R" if q[j] >= qp else "M") for j, qs, ps, qt, qp in self.fans)

    def step(self, q, p, R, g):
        h, d = self.law(q, R)
        r1 = h - self.At @ p; r2 = self.A @ q
        self.K.data[self.diag] = d + g
        sol = spl.splu(self.K).solve(-np.concatenate([r1, r2]))
        return sol[:self.B], sol[self.B:], max(np.abs(r1).max(), np.abs(r2).max()), d

    def newton(self, q, p, R, maxit=25, tol=1e-7):
        for it in range(maxit):
            dq, dp, res, d = self.step(q, p, R, 1e-12)
            if res < tol: return q, p, True
            m = np.abs(dq).max(); f = min(1.0, 40.0 / m) if m > 0 else 1.0
            q = q + f * dq; p = p + f * dp
        return q, p, False

    def settle(self, q, p, R, cap=4.0, tol=1e-7, maxit=6000):
        dt = 0.05
        for it in range(maxit):
            h, d = self.law(q, R)
            neg = d[d < 0]
            if neg.size: dt = min(dt, 0.5 / (-neg.min()))
            while True:
                dq, dp, res, d = self.step(q, p, R, 1.0 / dt)
                if res < tol: return q, p
                if np.abs(dq).max() > cap and dt > 1e-9: dt *= 0.5; continue
                break
            q = q + dq; p = p + dp; dt = min(dt * (10.0 if np.abs(dq).max() < 0.1 * cap else 2.0), 1e9)
        raise RuntimeError("flow did not settle")

    def change(self, q, p, R, j, r_new, substeps=12, stepped=False):
        r_old = R[j]; before = self.limbs(q)
        R[j] = r_new
        if not stepped:
            q1, p1, ok = self.newton(q, p, R)
            if ok and self.limbs(q1) == before: return q1, p1
        for s in range(1, substeps + 1):
            R[j] = r_old * (r_new / r_old) ** (s / substeps)
            q, p = self.settle(q, p, R)
        return q, p

    def carry(self, fixed, resume=None, stop_after=None):
        """The district through its log with these resistances for airways, stoppings and fan ducts.
        Returns the flows at every survey round, the flows at the end, and a snapshot before every large change.
        resume = (event number, q, p, settings resistances): start there, the large change taken in steps."""
        rounds = sorted({t for _, t, _ in self.points})
        seq = sorted([(t, 0, x, v) for t, x, v in self.events] + [(t, 1, None, None) for t in rounds])
        at = {}; snaps = []
        if resume is None:
            R = fixed.copy()
            for x, v in self.opening: R[self.item_branch[x]] = self.res(x, v)
            q = np.ones(self.B); p = np.zeros(self.N)
            for j, qs, ps, qt, qp in self.fans: q[j] = 0.75 * qs[-1]
            q, p, ok = self.newton(q, p, R)
            if not ok or self.limbs(q) != "R" * len(self.fans):
                q = np.ones(self.B); p = np.zeros(self.N)
                for j, qs, ps, qt, qp in self.fans: q[j] = 0.75 * qs[-1]
                q, p = self.settle(q, p, R)
            first = 0
        else:
            first, q, p, Rset = resume
            R = fixed.copy(); var = np.array(sorted(self.item_branch.values())); R[var] = Rset[var]
            q, p, ok = self.newton(q, p, R)
            if not ok: q, p = self.settle(q, p, R)
        for n in range(first, len(seq)):
            t, kind, x, v = seq[n]
            if kind == 0:
                j = self.item_branch[x]; r_new = self.res(x, v)
                large = max(r_new / R[j], R[j] / r_new) > 3.0
                if large and resume is None: snaps.append((n, q.copy(), p.copy(), R.copy(), self.limbs(q)))
                q, p = self.change(q, p, R, j, r_new, stepped=(resume is not None and n == first))
                if stop_after is not None and n == stop_after: return at, q, snaps
            else: at[t] = q.copy()
        return at, q, snaps

def main(folder, out):
    d = District(folder)
    latest, altered = d.on_file()
    found = d.breached() if MODE in ("full", "stopping", "derive") else {}
    order = list(altered)
    if MODE in ("full", "stopping"): order += [s for s in found if len(order) < d.allowance]
    fan = None
    if MODE in ("full", "fan", "derive") and len(order) < d.allowance:
        fan = max(d.fans, key=lambda f: float(d.br[f[0]]["resistance_Ns2_m8"])); order.append(d.names[fan[0]])   # the fan behind the longer ducting
    got = d.survey(order)
    fixed = np.zeros(d.B); air = np.zeros(d.B, bool)
    for j, r in enumerate(d.br):
        nm = r["branch"]
        if r["kind"] == "airway":
            dp, q = got[nm] if nm in got else (None, None)
            fixed[j] = dp / (q * abs(q)) if nm in got else latest[nm][1]; air[j] = True
        elif r["kind"] == "stopping":
            if nm in got: dp, q = got[nm]; fixed[j] = dp / (q * abs(q))
            elif nm in found: fixed[j] = found[nm]
            else: fixed[j] = float(r["resistance_Ns2_m8"])
        elif r["kind"] == "fan": fixed[j] = float(r["resistance_Ns2_m8"])
    at, q_end, snaps = d.carry(fixed)
    if fan is not None:
        j, qs, ps, qt, qp = fan; q_now = got[d.names[j]][1]
        limb = lambda q: "L" if q <= qt else ("R" if q >= qp else "M")
        if limb(q_now) != limb(q_end[j]):
            # the calculation ends on another limb than the fan is on: some large change went the other way in the
            # district than on the records. Going back from the end, the first large change whose outcome turns when
            # the airways' resistances are moved by up to 1.2 per cent is taken to be the one, with the least move
            # that turns it, and the record is carried on from there.
            def after(n, q0, p0, R0, s, whole=False):
                f2 = fixed.copy(); f2[air] *= 1.0 + s
                return d.carry(f2, resume=(n, q0, p0, R0), stop_after=None if whole else n)
            for n, q0, p0, R0, before in reversed(snaps[-10:]):
                base = d.limbs(after(n, q0, p0, R0, 0.0)[1]); sign = 0
                for sg in (1.0, -1.0):
                    if d.limbs(after(n, q0, p0, R0, sg * 0.012)[1]) != base: sign = sg; break
                if not sign: continue
                lo, hi = 0.0, 0.012
                for _ in range(6):
                    mid = 0.5 * (lo + hi)
                    if d.limbs(after(n, q0, p0, R0, sign * mid)[1]) != base: hi = mid
                    else: lo = mid
                at2, q2, _ = after(n, q0, p0, R0, sign * (hi + 0.0002), whole=True)
                if limb(q2[j]) == limb(q_now): at.update(at2)
                break
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["point", "flow_m3_s"])
        for pt, t, j in d.points: w.writerow([pt, "%.4f" % at[t][j]])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
