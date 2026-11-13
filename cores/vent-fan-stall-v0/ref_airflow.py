"""ref_airflow.py PACKAGE_DIR OUT_CSV: airflow at every survey point of a district package, to VS-4.

The district's state is carried through the log. Nodal-flow form: unknowns are every branch flow and every
node pressure. A change with every fan staying on its limb of the characteristic is one Newton solve from
the state before it. A change on which a fan leaves its limb is taken in small steps of the resistance, the
flow settling after each by implicit Euler on the inertial equations, so the district goes where the air
takes it when the state it was in ceases to exist.
"""
import csv, os, sys
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

def read(folder, name):
    with open(os.path.join(folder, name), newline="") as f: return list(csv.DictReader(f))

class District:
    def __init__(self, folder):
        br = read(folder, "branches.csv")
        self.names = [r["branch"] for r in br]; self.B = B = len(br)
        nodes = {"ATM": -1}
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
        self.fixed = np.array([float(r["resistance_Ns2_m8"]) if r["resistance_Ns2_m8"] else 0.0 for r in br])
        self.item_branch = {r["item"]: j for j, r in enumerate(br) if r["kind"] in ("regulator", "door")}
        self.reg = {}
        for r in read(folder, "regulators.csv"): self.reg[(r["regulator"], int(r["setting"]))] = float(r["resistance_Ns2_m8"])
        self.door = {r["door"]: (float(r["resistance_closed_Ns2_m8"]), float(r["resistance_open_Ns2_m8"])) for r in read(folder, "doors.csv")}
        curves = {}
        for r in read(folder, "fan_curves.csv"):
            c = curves.setdefault((r["model"], r["blade_setting"]), ([], [])); c[0].append(float(r["flow_m3_s"])); c[1].append(float(r["pressure_Pa"]))
        idx = {n: j for j, n in enumerate(self.names)}
        self.fans = []
        for r in read(folder, "fans.csv"):
            qs, ps = (np.array(v) for v in curves[(r["model"], r["blade_setting"])])
            k = 1
            while k < len(qs) - 1 and not (ps[k] < ps[k - 1] and ps[k] <= ps[k + 1]): k += 1
            kt = k
            while k < len(qs) - 1 and ps[k + 1] > ps[k]: k += 1
            self.fans.append((idx[r["branch"]], qs, ps, qs[kt], qs[k]))
        self.idx = idx
        log = read(folder, "log.csv"); t0 = log[0]["time"]
        self.R = self.fixed.copy()
        for r in log:
            if r["time"] == t0: self.R[self.item_branch[r["item"]]] = self.res(r["item"], r["setting"])
        self.events = [(r["time"], r["item"], r["setting"]) for r in log if r["time"] != t0]
        self.points = [(r["point"], r["time"], idx[r["branch"]]) for r in read(folder, "points.csv")]
        # sparsity pattern of the Newton matrix [[G, -A^T], [A, 0]] with G diagonal, built once
        K = sp.bmat([[sp.identity(B), -self.At], [self.A, None]], format="csc")
        self.K = K; K.sort_indices()
        self.diag = np.array([K.indptr[j] + int(np.searchsorted(K.indices[K.indptr[j]:K.indptr[j + 1]], j)) for j in range(B)])

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

    def step(self, q, p, R, g_extra):
        """One linearised step with g_extra added to the branch slopes (inertia over the time step)."""
        h, d = self.law(q, R)
        r1 = h - self.At @ p; r2 = self.A @ q
        self.K.data[self.diag] = d + g_extra
        sol = spl.splu(self.K).solve(-np.concatenate([r1, r2]))
        return sol[:self.B], sol[self.B:], max(np.abs(r1).max(), np.abs(r2).max()), d

    def newton(self, q, p, R, maxit=25, tol=1e-7):
        for it in range(maxit):
            dq, dp, res, d = self.step(q, p, R, 1e-12)
            if res < tol: return q, p, True
            m = np.abs(dq).max(); f = min(1.0, 40.0 / m) if m > 0 else 1.0
            q = q + f * dq; p = p + f * dp
        return q, p, False

    def settle(self, q, p, R, cap=4.0, tol=1e-7, maxit=4000):
        """Implicit Euler on the inertial equations (unit inertance in every branch) until the flow is steady."""
        dt = 0.05
        for it in range(maxit):
            h, d = self.law(q, R)
            neg = d[d < 0]
            if neg.size: dt = min(dt, 0.5 / (-neg.min()))      # keeps the step a descent while a fan is on a rising limb
            while True:
                dq, dp, res, d = self.step(q, p, R, 1.0 / dt)
                if res < tol: return q, p
                if np.abs(dq).max() > cap and dt > 1e-9: dt *= 0.5; continue
                break
            q = q + dq; p = p + dp; dt = min(dt * 2.0, 1e9)
        raise RuntimeError("flow did not settle")

    def change(self, q, p, j, r_new, substeps=12):
        R = self.R; r_old = R[j]; before = self.limbs(q)
        R[j] = r_new
        q1, p1, ok = self.newton(q, p, R)
        if ok and self.limbs(q1) == before: return q1, p1
        for s in range(1, substeps + 1):                      # a fan leaves its limb: follow the change
            R[j] = r_old * (r_new / r_old) ** (s / substeps)
            q, p = self.settle(q, p, R)
        return q, p

def main(folder, out):
    d = District(folder)
    q = np.ones(d.B); p = np.zeros(d.N)
    for j, qs, ps, qt, qp in d.fans: q[j] = 0.75 * qs[-1]
    q, p, ok = d.newton(q, p, d.R)
    if not ok: q, p = d.settle(q, p, d.R)
    rounds = sorted({t for _, t, _ in d.points}); at = {}
    seq = sorted([(t, 0, x, v) for t, x, v in d.events] + [(t, 1, None, None) for t in rounds])
    for t, kind, x, v in seq:
        if kind == 0: q, p = d.change(q, p, d.item_branch[x], d.res(x, v))
        else: at[t] = q.copy()
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["point", "flow_m3_s"])
        for pt, t, j in d.points: w.writerow([pt, "%.4f" % at[t][j]])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
