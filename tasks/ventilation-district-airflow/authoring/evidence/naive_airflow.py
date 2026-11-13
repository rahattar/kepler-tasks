"""naive_airflow.py PACKAGE_DIR OUT_CSV: a second way to the same airflows, written apart from the reference.

It does not solve the district and its fans together. With the fans taken out, every branch of a district
obeys the same square law, so the district seen from the fan house is one resistance, and every branch
carries a fixed share of whatever the fans deliver. So:

  - for every state of the regulators and doors the district is solved alone, between the surface and the
    fan house, by the linear-theory iteration (each pass a full linear solve with the resistances
    linearised about the last flows), started from scratch every time;
  - the fans are then a small system of their own: each fan's pressure less its ducting loss equals the
    district's resistance times the square of their total flow. It is carried through the record with a
    little inertia on each fan, the district's resistance moved gradually from one state to the next.

Nothing is cached and nothing is sparse, which is what makes it slow.

The records are read as the reference reads them, but worked differently: a stopping is judged by the air
that the two gate roads at its intake end do not account for, the fan is read when a survey is left over,
and when the fan is not where the calculation ends, the last large movement at the stall point (a fan
changed limb at it, or was left within 5 per cent of its peak) whose outcome a 1.2 per cent change of the
district's resistance reverses is the one that is turned.
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

def district_alone(nodes, ends, R, fan_house):
    """The passive district with 1 Pa of suction at the fan house: every branch flow, by linear theory."""
    n = len(nodes); free = [i for i in range(n) if i not in (nodes["ATM"], fan_house)]
    pos = {node: k for k, node in enumerate(free)}
    q = np.ones(len(ends)); p = np.zeros(n); p[fan_house] = -1.0
    for sweep in range(200):
        g = 1.0 / (R * np.maximum(np.abs(q), 1e-9))                 # conductance of each branch about the last flow
        A = np.zeros((len(free), len(free))); b = np.zeros(len(free))
        for j, (u, v) in enumerate(ends):
            for x, y in ((u, v), (v, u)):
                if x in pos:
                    A[pos[x], pos[x]] += g[j]
                    if y in pos: A[pos[x], pos[y]] -= g[j]
                    else: b[pos[x]] += g[j] * p[y]
        p[free] = np.linalg.solve(A, b)
        new = np.array([g[j] * (p[u] - p[v]) for j, (u, v) in enumerate(ends)])
        if sweep and np.abs(new - q).max() < 1e-10 * np.abs(new).max(): q = new; break
        q = 0.5 * (q + new) if sweep else new
    return q

def fans_settle(curves, legs, r, q, steps=200000):
    """The fans against a district of resistance r, from flows q: each fan's flow moves with its surplus pressure."""
    q = np.array(q, float); dt = 2e-3
    for _ in range(steps):
        total = q.sum()
        f = np.array([fan_pressure(c, x) - l * x * abs(x) - r * total * abs(total) for c, l, x in zip(curves, legs, q)])
        if np.abs(f).max() < 1e-7: break
        q = q + np.clip(dt * f, -0.5, 0.5)
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
    def seen_from_fans(R):
        q = district_alone(nodes, ends, R[passive], fan_house)
        total = sum(q[k] for k, (u, v) in enumerate(ends) if v == fan_house) - sum(q[k] for k, (u, v) in enumerate(ends) if u == fan_house)
        return 1.0 / total ** 2, q / total                    # the district's resistance, and each branch's share of the fans' air
    log = rows(folder, "log.csv"); t0 = log[0]["time"]
    for r in log:
        if r["time"] == t0: R[where[r["item"]]] = setting(r["item"], r["setting"])
    points = rows(folder, "points.csv")
    rounds = sorted({r["time"] for r in points})
    marks = [stall_marks(c) for c in curves]
    def limb(i, q): return "L" if q <= marks[i][0] else ("R" if q >= marks[i][1] else "M")

    def carry(turn=None):
        """Through the record. turn = (index of a log row, factor): from that movement on the district's resistance
        is taken that much higher or lower, which is how a movement at the stall point is made to go the other way."""
        Rn = R.copy()
        r_now, share = seen_from_fans(Rn)
        q = fans_settle(curves, legs, r_now, [0.75 * c[0][-1] for c in curves])
        flows = {}; large = []; scale = 1.0
        todo = sorted([(r["time"], 0, i) for i, r in enumerate(log) if r["time"] != t0] + [(t, 1, None) for t in rounds])
        for t, kind, i in todo:
            if kind == 1:
                full = np.zeros(len(br)); full[passive] = share * q.sum(); full[fan_branch] = q
                flows[t] = full; continue
            row = log[i]; j = where[row["item"]]; old = Rn[j]; Rn[j] = setting(row["item"], row["setting"])
            before = [limb(k, x) for k, x in enumerate(q)]
            r_next, share = seen_from_fans(Rn)
            if turn and turn[0] == i: scale = turn[1]
            r_next *= scale
            for s in range(1, 13):
                q = fans_settle(curves, legs, r_now * (r_next / r_now) ** (s / 12.0), q)
            if max(Rn[j] / old, old / Rn[j]) > 3.0:
                # a large movement is a candidate for the turn if a fan changed limb at it, or a healthy fan was
                # left within 5 per cent of the quantity at its peak
                room = min([(x - marks[k][1]) / marks[k][1] for k, x in enumerate(q) if x >= marks[k][1]] or [0.0])
                if before != [limb(k, x) for k, x in enumerate(q)] or room < 0.05: large.append(i)
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
