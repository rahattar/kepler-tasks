#!/usr/bin/env python3
"""Peak shaft-line torques and coupling temperatures through a set's speed transients, to TS-4.

    python3 peaks.py SET_DIR OUT_CSV

The response is a fast oscillation at each excitation order riding on a slow sweep of speed and a slower drift
of the coupling's stiffness as its rubber heats. Integrating the equations of motion step by step has to
resolve the fastest oscillation over the whole sequence: millions of steps. Here each order's response is
carried as a complex amplitude that changes slowly (its envelope) and is integrated in slow time:

1. The rigid acceleration of the line during a ramp loads it quasi-statically; that twist is solved at each
   slow step.
2. For each order k the displacement is x_k = Re(Q_k exp(i k phi)). Put into the equations of motion this
   gives J Q'' + (2 i k w J + C) Q' + B Q = F, linear in Q because the line is linear at every instant; only
   the coupling's stiffness in B moves, with the rubber temperature. Q'' is small: the first pass drops it,
   the second puts back the Q'' of the first. Each pass is the trapezoidal rule.
3. The rubber's temperature follows the power the coupling dissipates, averaged over the cycle, from the
   envelopes, and its cooling; it is carried from each run into the next.
4. The torques are put back together in time from the envelopes, only where the sum of their amplitudes could
   reach the largest torque found so far, and each peak is refined by a parabola through its samples.
"""
import csv
import json
import os
import sys

import numpy as np

LEAD_S = 1.0
RAMP_STEPS = 800           # slow steps over a run's lead and ramp
HOLD_STEP_S = 0.25          # slow step over a hold
SAMPLES_PER_PERIOD = 30     # in the reconstruction


def speed(t, r):
    """Speed (rad/s), angle from the run's start (rad) and acceleration (rad/s2) at times t within run r."""
    wa, wb, D = r["n_start_rpm"] * np.pi / 30, r["n_end_rpm"] * np.pi / 30, r["ramp_s"]
    x = np.clip((t - LEAD_S) / D, 0.0, 1.0)
    w = wa + (wb - wa) * (x - np.sin(2 * np.pi * x) / (2 * np.pi))
    acc = np.where((t > LEAD_S) & (t < LEAD_S + D), (wb - wa) / D * (1 - np.cos(2 * np.pi * x)), 0.0)
    before = wa * np.minimum(t, LEAD_S)
    during = D * (wa * x + (wb - wa) * (x * x / 2 + (np.cos(2 * np.pi * x) - 1) / (4 * np.pi ** 2)))
    after = wb * np.maximum(t - LEAD_S - D, 0.0)
    return w, before + during + after, acc


def solve(M, b):
    return np.linalg.solve(M, b[..., None])[..., 0]


class Line:
    def __init__(self, line):
        self.J = np.array([line["inertia_kgm2"][k] for k in ("engine", "flywheel", "hub", "generator")])
        self.Jm = np.diag(self.J)
        cp = line["coupling"]
        self.k12, self.c12 = line["crankshaft"]["stiffness_Nm_per_rad"], line["crankshaft"]["damping_Nms_per_rad"]
        self.k34, self.c34 = line["generator_shaft"]["stiffness_Nm_per_rad"], line["generator_shaft"]["damping_Nms_per_rad"]
        self.k_ref, self.c23, self.soft, self.T_ref = (cp["stiffness_Nm_per_rad"], cp["damping_Nms_per_rad"],
                                                       cp["softening_per_K"], cp["reference_C"])
        self.heat_cap, self.cool, self.T_amb = cp["heat_capacity_J_per_K"], cp["cooling_W_per_K"], line["ambient_C"]
        self.T0 = line["start_C"]
        self.orders = np.array([o["order"] for o in line["orders"]])
        self.F = np.zeros((len(self.orders), 4), complex)
        self.F[:, 0] = -1j * np.array([o["amplitude_Nm"] for o in line["orders"]]) * np.exp(
            1j * np.deg2rad([o["phase_deg"] for o in line["orders"]]))
        self.pattern = np.zeros((4, 4))
        self.pattern[1, 1] = self.pattern[2, 2] = 1.0
        self.pattern[1, 2] = self.pattern[2, 1] = -1.0
        self.K0 = np.zeros((4, 4))
        for (a, b), k in (((0, 1), self.k12), ((2, 3), self.k34)):
            self.K0[a, a] += k; self.K0[b, b] += k; self.K0[a, b] -= k; self.K0[b, a] -= k
        C = np.zeros((4, 4))
        for (a, b), c in (((0, 1), self.c12), ((1, 2), self.c23), ((2, 3), self.c34)):
            C[a, a] += c; C[b, b] += c; C[a, b] -= c; C[b, a] -= c
        C[0, 0] += line["engine_damping_Nms_per_rad"]
        self.C = C
        # the line's rigid mode carries no torque, and in the envelope equations, which drop Q'', it would be an
        # undamped oscillation at half the forcing frequency: the envelopes are carried in the three-dimensional
        # space of motions with no net angular momentum, sum(J q) = 0, spanned by the columns of Phi
        u, _, vt = np.linalg.svd(self.J[None, :])
        self.Phi = vt[1:].T                                              # (4, 3), J @ Phi = 0
        self.Jr = self.Phi.T @ self.Jm @ self.Phi
        self.Cr = self.Phi.T @ self.C @ self.Phi
        self.Kr0 = self.Phi.T @ self.K0 @ self.Phi
        self.Pr = self.Phi.T @ self.pattern @ self.Phi
        self.Fr = self.F @ self.Phi

    def modes(self, T):
        """Eigenvalues and eigenvectors of the reduced line's state matrix at rubber temperature T."""
        K = self.Kr0 + self.k23(T) * self.Pr
        Mi = np.linalg.inv(self.Jr)
        A = np.block([[np.zeros((3, 3)), np.eye(3)], [-Mi @ K, -Mi @ self.Cr]])
        lam, V = np.linalg.eig(A)
        self.T_modes = T
        return lam, V, np.linalg.inv(V)

    def k23(self, T):
        return self.k_ref * np.exp(-self.soft * (T - self.T_ref))

    def system(self, w, acc, T):
        """A Y' + B Y = Phi' F for every order, in the reduced coordinates."""
        kw = self.orders * w
        K = self.Kr0 + self.k23(T) * self.Pr
        A = 2j * kw[:, None, None] * self.Jr + self.Cr
        B = K - (kw ** 2)[:, None, None] * self.Jr + 1j * (self.orders * acc)[:, None, None] * self.Jr \
            + 1j * kw[:, None, None] * self.Cr
        return A, B

    def static(self, acc, T):
        """Quasi-static displacement from the rigid acceleration (q1 held at 0)."""
        load = -acc * self.J
        load[0] += self.J.sum() * acc
        K = self.K0 + self.k23(T) * self.pattern
        q = np.zeros(4)
        q[1:] = np.linalg.solve(K[1:, 1:], load[1:])
        return q


def run_envelopes(L, r, X0, T0, F):
    """Envelopes of one run. X is each order's complex state, [y; y'] in the reduced coordinates, with the state
    itself Re(X exp(i k phi)). From x' = A x + B f this is exactly X' = (A - i k w I) X + B F: first order, with
    nothing dropped. In the eigenvectors of A each component is Y' = (lambda - i k w) Y + G; it is stepped by its
    exponential with the coefficient taken at the middle of the step. Components near resonance change slowly;
    the others rotate fast about their steady value and stay on it. Returns the slow grid, speeds, angles,
    displacement and velocity envelopes in the full coordinates, the quasi-static displacement, the
    temperatures and the end state X."""
    lead_ramp = LEAD_S + r["ramp_s"]
    t = np.linspace(0.0, lead_ramp, RAMP_STEPS + 1)
    if r["hold_s"] > 0:
        n_hold = max(4, int(np.ceil(r["hold_s"] / HOLD_STEP_S)))
        t = np.concatenate([t, lead_ramp + np.linspace(0.0, r["hold_s"], n_hold + 1)[1:]])
    w, phi, acc = speed(t, r)
    n = len(t)
    X = np.empty((n,) + X0.shape, complex)
    T = np.empty(n)
    X[0], T[0] = X0, T0
    G_in = np.concatenate([np.zeros_like(F), np.linalg.solve(L.Jr, F.T).T], axis=1)       # B F, (orders, 6)
    g = L.cool / L.heat_cap

    def power(Xi):
        v = Xi[:, 3:] @ L.Phi.T
        return 0.5 * L.c23 * np.sum(np.abs(v[:, 1] - v[:, 2]) ** 2)

    P_old = power(X0)
    lam, V, Vi = L.modes(T0)
    for i in range(1, n):
        h = t[i] - t[i - 1]
        # the temperature, with the power of the step before; then again with the mean power over the step
        T[i] = (T[i - 1] * (1 - 0.5 * h * g) + h * (P_old / L.heat_cap + g * L.T_amb)) / (1 + 0.5 * h * g)
        if abs(T[i] - L.T_modes) > 0.05:
            lam, V, Vi = L.modes(T[i])
        mu = lam[None, :] - 1j * L.orders[:, None] * 0.5 * (w[i] + w[i - 1])                # (orders, 6)
        Y = (Vi @ X[i - 1][..., None])[..., 0]
        G = (Vi @ G_in[..., None])[..., 0]
        e = np.exp(mu * h)
        Y = e * Y + (e - 1) / mu * G
        X[i] = (V @ Y[..., None])[..., 0]
        P_new = power(X[i])
        T[i] = (T[i - 1] * (1 - 0.5 * h * g) + h * (0.5 * (P_old + P_new) / L.heat_cap + g * L.T_amb)) / (1 + 0.5 * h * g)
        P_old = P_new
    qs = np.array([L.static(a, Ti) for a, Ti in zip(acc, T)])
    return t, w, phi, X[..., :3] @ L.Phi.T, X[..., 3:] @ L.Phi.T, qs, T, X[-1]


def run_peaks(L, r, t, env, venv, qs, T):
    """Peak torques (Nm) of one run from its envelopes."""
    stiff = np.stack([np.full(len(t), L.k12), L.k23(T), np.full(len(t), L.k34)], axis=1)       # (slow, 3)
    damp = np.array([L.c12, L.c23, L.c34])
    w, _, _ = speed(t, r)
    rel = env[..., :3] - env[..., 1:]                                                       # (slow, orders, 3)
    vrel = venv[..., :3] - venv[..., 1:]
    bound = (np.abs(stiff[:, None] * rel + damp * vrel).sum(axis=1) + np.abs(stiff * (qs[:, :3] - qs[:, 1:]))) * 1.05
    top_w = max(np.sqrt(np.max(np.linalg.eigvals((L.K0 + 2 * L.k_ref * L.pattern) / L.J[:, None]).real)),
                L.orders.max() * max(r["n_start_rpm"], r["n_end_rpm"]) * np.pi / 30)
    fine = 2 * np.pi / top_w / SAMPLES_PER_PERIOD
    best = np.zeros(3)
    span = np.maximum(bound[:-1], bound[1:])                                                # (intervals, 3)
    for e in range(3):
        order_ = np.argsort(-span[:, e])
        done = 0
        while done < len(order_) and span[order_[done], e] > best[e]:
            pick = order_[done:done + 32]
            pick = pick[span[pick, e] > best[e]]
            done += 32
            for k in pick:
                per = int(np.ceil((t[k + 1] - t[k]) / fine)) + 2
                fr = np.linspace(0.0, 1.0, per)
                tf = t[k] + fr * (t[k + 1] - t[k])
                wf, pf, _ = speed(tf, r)
                f = fr[:, None, None]
                ek = env[k] * (1 - f) + env[k + 1] * f
                vk = venv[k] * (1 - f) + venv[k + 1] * f
                rot = np.exp(1j * L.orders[None, :] * pf[:, None])[..., None]
                x = (ek * rot).sum(axis=1).real + qs[k] * (1 - fr[:, None]) + qs[k + 1] * fr[:, None]
                v = (vk * rot).sum(axis=1).real
                kk = stiff[k, e] * (1 - fr) + stiff[k + 1, e] * fr
                tq = np.abs(kk * (x[:, e] - x[:, e + 1]) + damp[e] * (v[:, e] - v[:, e + 1]))
                i = int(np.clip(np.argmax(tq), 1, per - 2))
                y0, y1, y2 = tq[i - 1], tq[i], tq[i + 1]
                den = y0 - 2 * y1 + y2
                top = y1 - (y0 - y2) ** 2 / (8 * den) if (den < 0 and y1 >= y0 and y1 >= y2) else y1
                best[e] = max(best[e], top)
    return best


def set_results(line, runs):
    L = Line(line)
    # the settled response at the first run's starting speed, rubber at the set's starting temperature
    w0 = runs[0]["n_start_rpm"] * np.pi / 30
    lam, V, Vi = L.modes(L.T0)
    G_in = np.concatenate([np.zeros_like(L.Fr), np.linalg.solve(L.Jr, L.Fr.T).T], axis=1)
    mu = lam[None, :] - 1j * L.orders[:, None] * w0
    Q = (V @ (-(Vi @ G_in[..., None])[..., 0] / mu)[..., None])[..., 0]                  # X' = 0: the steady state
    T = L.T0
    angle = 0.0                    # the engine's angle at the start of the run: the excitation's phase goes on
    out = []
    for r in runs:
        F = L.Fr * np.exp(1j * L.orders * angle)[:, None]
        t, w, phi, env, slope, qs, Ts, last = run_envelopes(L, r, Q, T, F)
        out.append((run_peaks(L, r, t, env, slope, qs, Ts), Ts[-1]))
        # the next run's envelopes are taken against its own angle, which starts at 0
        Q, T = last * np.exp(1j * L.orders * phi[-1])[:, None], Ts[-1]
        angle += phi[-1]
    return out


def main(set_dir, destination):
    with open(os.path.join(set_dir, "shaftline.json")) as handle:
        line = json.load(handle)
    with open(os.path.join(set_dir, "runs.csv"), newline="") as handle:
        runs = [dict(run=r["run"], n_start_rpm=float(r["n_start_rpm"]), n_end_rpm=float(r["n_end_rpm"]),
                     ramp_s=float(r["ramp_s"]), hold_s=float(r["hold_s"])) for r in csv.DictReader(handle)]
    results = set_results(line, runs)
    with open(destination, "w", newline="") as handle:
        table = csv.writer(handle, lineterminator="\n")
        table.writerow(["run", "crankshaft_kNm", "coupling_kNm", "generator_shaft_kNm", "rubber_C"])
        for run, (p, T) in zip(runs, results):
            table.writerow([run["run"]] + ["%.4f" % (v / 1e3) for v in p] + ["%.3f" % T])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python3 peaks.py SET_DIR OUT_CSV")
    main(sys.argv[1], sys.argv[2])
