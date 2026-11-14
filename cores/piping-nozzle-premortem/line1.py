import numpy as np
from proto import route, Line
OD, WALL = 0.457, 0.045
W = 5.46e3          # N/m pipe + insulation
R = 1.5 * OD
PTS = [(32, 18, 58), (32, 18, 30), (12, 18, 30), (12, 4, 30), (12, 4, 16), (3, 4, 16), (3, 0, 16), (0, 0, 16)]
xyz, elems = route(PTS, R)
def node_at(p):
    return int(np.argmin(np.linalg.norm(xyz - np.array(p, float), axis=1)))
SUP = [  # name, kind, where
    ("H1", "spring", (32, 18, 50)), ("H2", "spring", (32, 18, 38)),
    ("H3", "spring", (26, 18, 30)), ("H4", "spring", (20, 18, 30)), ("H5", "spring", (14, 18, 30)),
    ("H6", "spring", (12, 11, 30)), ("G1", "guide", (12, 8, 30), "x"), ("H7", "spring", (12, 6, 30)),
    ("H8", "spring", (12, 4, 23)),
    ("R1", "rod", (8, 4, 16)), ("G2", "guide", (6, 4, 16), "y"),
    ("H9", "spring", (3, 2, 16)),
]
def supports(gap=0.003):
    out = []
    for s in SUP:
        d = dict(name=s[0], kind=s[1], node=node_at(s[2]))
        if s[1] == "guide":
            d.update(dir=s[3], gap=gap)
        out.append(d)
    return out
STATES = {"cold": (20.0, np.zeros(3), np.zeros(3)),
          "hot_60": (535.0, np.array([0.0, 0.0, -0.045]), np.array([0.0, 0.0, 0.004])),
          "hot_80": (550.0, np.array([0.0, 0.0, -0.052]), np.array([0.0, 0.0, 0.005])),
          "hot_100": (565.0, np.array([0.0, 0.0, -0.060]), np.array([0.0, 0.0, 0.006])),
          "design": (580.0, np.array([0.0, 0.0, -0.066]), np.array([0.0, 0.0, 0.007]))}

def design_springs(line):
    """Hot loads: the weight on rigid supports at the hangers. Travel: the hot_100 run with the hangers as
    constant forces at their hot loads. Rate: the largest catalogue rate with variability at most 25 per cent.
    Cold load = hot load + rate * travel (travel up positive), so that F = Fc - k u_z gives the hot load hot."""
    sup = line.sup
    for s in sup:
        if s["kind"] == "spring":
            s["rate"], s["cold_load"] = 1e12, 0.0
    u, _, _ = line.solve(20.0, np.zeros(3), np.zeros(3))
    hot = {s["name"]: -1e12 * u[6 * s["node"] + 2] for s in sup if s["kind"] == "spring"}
    for s in sup:
        if s["kind"] == "spring":
            s["rate"], s["cold_load"] = 0.0, hot[s["name"]]
    T, dA, dB = STATES["hot_100"]
    uc, _, act = line.solve(20.0, np.zeros(3), np.zeros(3))
    uh, _, _ = line.solve(T, dA, dB, state=act)
    cat = np.array([50, 70, 100, 140, 200, 280, 400, 560, 800, 1120, 1600, 2240, 3200]) * 1e3   # N/m
    for s in sup:
        if s["kind"] == "spring":
            trav = uh[6 * s["node"] + 2]
            need = 0.25 * hot[s["name"]] / max(abs(trav), 1e-3)
            rate = cat[cat <= need].max() if (cat <= need).any() else cat[0]
            s["rate"], s["travel"], s["hot_load"] = float(rate), float(trav), float(hot[s["name"]])
            s["cold_load"] = float(hot[s["name"]] + rate * trav)
    return sup

def build(gap=0.003):
    line = Line(xyz, elems, OD, WALL, W, R, supports(gap))
    design_springs(line)
    return line
