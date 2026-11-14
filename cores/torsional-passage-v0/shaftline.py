"""The sealed definition: a generating set's shaft line through a sequence of speed transients.

`simulate` integrates the equations of motion of TS-4 in time over a set's whole sequence of runs, with the
rubber of the coupling heating by the power it dissipates and softening as it heats, by the classical
Runge-Kutta rule at STEPS_PER_PERIOD steps to the period of the highest frequency the line can respond at.
It returns each run's peak crankshaft, coupling and generator shaft torques, each refined by a parabola through
the largest sample and its neighbours, and the rubber temperature at the end of each run. Before the record
starts the line is held at the first run's starting speed for SETTLE_S seconds from rest, with the rubber at
the set's starting temperature, so that the record begins in the settled response (TS-4). This is the truth
the verifier holds a program to; it is never a run of the reference solution.
"""
import numpy as np

SETTLE_S = 4.0
LEAD_S = 1.0             # TS-4: every run holds its starting speed for one second before its ramp
STEPS_PER_PERIOD = 30


def schedule(runs):
    """Start time, ramp start, ramp end and end time of every run in the sequence (s)."""
    out, t = [], 0.0
    for r in runs:
        a = t + LEAD_S
        b = a + r["ramp_s"]
        e = b + r["hold_s"]
        out.append((t, a, b, e))
        t = e
    return np.array(out)


def kinematics(t, runs, times):
    """Engine speed (rad/s) and acceleration (rad/s2) at time t of the sequence."""
    j = int(np.clip(np.searchsorted(times[:, 3], t, side="left"), 0, len(runs) - 1))
    r, (t0, a, b, e) = runs[j], times[j]
    wa, wb, D = r["n_start_rpm"] * np.pi / 30, r["n_end_rpm"] * np.pi / 30, r["ramp_s"]
    x = min(max((t - a) / D, 0.0), 1.0)
    w = wa + (wb - wa) * (x - np.sin(2 * np.pi * x) / (2 * np.pi))
    acc = (wb - wa) / D * (1 - np.cos(2 * np.pi * x)) if a < t < b else 0.0
    return w, acc


def simulate(line, runs):
    """(peaks (runs, 3) in Nm: crankshaft, coupling, generator shaft; rubber temperature at each run's end, C)."""
    J = np.array([line["inertia_kgm2"][k] for k in ("engine", "flywheel", "hub", "generator")])
    k12, c12 = line["crankshaft"]["stiffness_Nm_per_rad"], line["crankshaft"]["damping_Nms_per_rad"]
    k34, c34 = line["generator_shaft"]["stiffness_Nm_per_rad"], line["generator_shaft"]["damping_Nms_per_rad"]
    cp = line["coupling"]
    k_ref, c23, soft, T_ref = cp["stiffness_Nm_per_rad"], cp["damping_Nms_per_rad"], cp["softening_per_K"], cp["reference_C"]
    heat_cap, cool, T_amb = cp["heat_capacity_J_per_K"], cp["cooling_W_per_K"], line["ambient_C"]
    c1 = line["engine_damping_Nms_per_rad"]
    orders = np.array([o["order"] for o in line["orders"]])
    amps = np.array([o["amplitude_Nm"] for o in line["orders"]])
    phases = np.deg2rad([o["phase_deg"] for o in line["orders"]])
    total = J.sum()
    times = schedule(runs)
    top_speed = max(max(r["n_start_rpm"], r["n_end_rpm"]) for r in runs) * np.pi / 30
    K = np.zeros((4, 4))
    for (a, b), k in (((0, 1), k12), ((1, 2), 2 * k_ref), ((2, 3), k34)):
        K[a, a] += k; K[b, b] += k; K[a, b] -= k; K[b, a] -= k
    wn = np.sqrt(np.max(np.linalg.eigvals(K / J[:, None]).real))
    h = 2 * np.pi / max(wn, orders.max() * top_speed) / STEPS_PER_PERIOD

    def deriv(t, s, settling):
        """s = [q1..q4, v1..v4, phi, T_rubber]."""
        q, v, phi, T = s[:4], s[4:8], s[8], s[9]
        if settling:
            w, acc = runs[0]["n_start_rpm"] * np.pi / 30, 0.0
        else:
            w, acc = kinematics(t, runs, times)
        k23 = k_ref * np.exp(-soft * (T - T_ref))
        d = q[:3] - q[1:]
        dv = v[:3] - v[1:]
        t12 = k12 * d[0] + c12 * dv[0]
        t23 = k23 * d[1] + c23 * dv[1]
        t34 = k34 * d[2] + c34 * dv[2]
        f = -acc * J
        f[0] += total * acc + (amps * np.sin(orders * phi + phases)).sum() - t12 - c1 * v[0]
        f[1] += t12 - t23
        f[2] += t23 - t34
        f[3] += t34
        out = np.empty(10)
        out[:4], out[4:8], out[8] = v, f / J, w
        out[9] = 0.0 if settling else (c23 * dv[1] ** 2 - cool * (T - T_amb)) / heat_cap
        return out

    def torques(s):
        q, v, T = s[:4], s[4:8], s[9]
        d = q[:3] - q[1:]
        dv = v[:3] - v[1:]
        k23 = k_ref * np.exp(-soft * (T - T_ref))
        return np.abs(np.array([k12 * d[0] + c12 * dv[0], k23 * d[1] + c23 * dv[1], k34 * d[2] + c34 * dv[2]]))

    def rk4(t, s, h, settling=False):
        a1 = deriv(t, s, settling)
        a2 = deriv(t + h / 2, s + h / 2 * a1, settling)
        a3 = deriv(t + h / 2, s + h / 2 * a2, settling)
        a4 = deriv(t + h, s + h * a3, settling)
        return s + h / 6 * (a1 + 2 * a2 + 2 * a3 + a4)

    s = np.zeros(10)
    s[9] = line["start_C"]
    s[8] = -runs[0]["n_start_rpm"] * np.pi / 30 * SETTLE_S        # so that the angle is 0 when the record starts
    n_settle = int(np.ceil(SETTLE_S / h))
    for _ in range(n_settle):
        s = rk4(0.0, s, SETTLE_S / n_settle, settling=True)
    peaks = np.zeros((len(runs), 3))
    temps = np.full(len(runs), np.nan)
    end = times[-1, 3]
    steps = int(np.ceil(end / h))
    h = end / steps
    older = torques(s)
    s = rk4(0.0, s, h)
    old = torques(s)
    j = 0
    for i in range(2, steps + 1):
        t_old = (i - 1) * h                       # the time of the sample `old`
        s = rk4(t_old, s, h)
        now = torques(s)
        while j < len(runs) - 1 and t_old > times[j, 3]:
            j += 1
        mid = (old >= older) & (old >= now)
        if mid.any():
            den = older - 2 * old + now
            ok = mid & (den < 0)
            top = np.where(ok, old - (older - now) ** 2 / (8 * np.where(ok, den, -1.0)), old)
            peaks[j] = np.maximum(peaks[j], np.where(mid, top, 0.0))
        for r in range(len(runs)):
            if np.isnan(temps[r]) and i * h >= times[r, 3] - 1e-9:
                temps[r] = s[9]
        older, old = old, now
    temps[np.isnan(temps)] = s[9]
    return peaks, temps
