"""Reference solution for skid-noise-guarantee.

    python3 solve.py DATA_DIR OUT_CSV

Uses only the documents in DATA_DIR and the booked instrument's `slm` and `rt` commands (3 readings).

1. The hall as it is. The acoustic report's reverberation time was measured when the hall was handed over, with the
   absorptive ceiling panels it lists among the hall's surfaces; the roof repair of June 2026 took the ceiling lining
   panels down for access and the second work order records that they were not refitted (maintenance log). The
   equivalent absorption area of each band therefore comes from a reverberation measurement made now, which the
   standard allows at one station because the field away from the machines is diffuse. That is one reading.
2. The machines as they are. The survey of 14 and 15 September 2026 recorded each machine as it then stood, and the
   four of them are referred to the present in three different ways.
   - C2's speed column gives 2508 rpm against its rated 2950 rpm, so its levels are referred to the rated speed by
     the standard's 50 lg rule. No reading is needed for it.
   - C1 and C3 were surveyed at their rated speed, and the log records work on each after the survey that changed
     what is fitted to it: C1's drive-end access cover was refitted on 2026-09-20, having been taken off for the oil
     change of 2026-09-11 and so standing open through the survey, and C3's intake silencer was installed on
     2026-10-02. Each therefore needs the standard's configuration difference: the per-band difference between a
     level measured now and the survey's level at one position of the machine's own array. That is one reading each,
     and with the reverberation measurement it is the whole booking of 3.
   - C4 was surveyed at its rated speed and the log records nothing done to it since but filters, oil and readings,
     so its survey stands as it is. A reading spent on it leaves one of the other two unmeasured.
3. The rows. The survey sheet enters four rows under the wrong machine: P7 and P8, the two ends of C1's array, appear
   under C2, and P13 and P14 of C2's array appear under C1. Both arrays were set at 3.0 m, so nothing but the
   position table gives it away, and the speed column of the four rows disagrees with the rest of the machine they
   are entered under. Rows are assigned to machines by the position table.
4. The levels. The first day's pass was read with M-5 and the second day's with M-2, which carried a windscreen; the
   meter column of each row says which, and the level with everything off at a position was read with the same
   instrument. Each level is corrected by its own instrument's certificate (M-2 +0.1, +0.7 and +2.4 dB at 2, 4 and
   8 kHz; M-5 and the booked M-7 nothing). The level with everything off is then subtracted in energy from the level
   with the machine running, position by position and band by band.
5. The positions. A position is valid when it lies on the machine's measurement surface and the level with the
   machine running exceeds the level with everything off by at least 6 dB in every band. P4 of C1's array was set at
   0.65 m instead of 3.0 m, and P15 and P16 of C2's array are by the louvred east wall, where the adjacent bay's
   blower leaves 250 Hz and 500 Hz below that margin; those three are dropped, which leaves 7, 6, 7 and 8 valid
   positions.
6. The surface. C3 stands 0.6 m from the east wall, inside the standard's 1.5 m, so it radiates into a quarter space
   and its surface is pi r^2; the others stand clear and theirs are 2 pi r^2. The radius is the one the array was set
   at, which for C3 is 2.0 m, not the 3.0 m the register gives as nominal.
7. The result. Lw = Lp + 10 lg S - K2 in each band, then the speed referral or the configuration difference, and the
   A-weighted level is the energy sum of the weighted bands.
"""
import csv
import math
import os
import re
import subprocess
import sys

LABEL = ["63", "125", "250", "500", "1k", "2k", "4k", "8k"]


def rows(data, name):
    with open(os.path.join(data, name), newline="") as f:
        return list(csv.DictReader(f))


def text(data, name):
    return open(os.path.join(data, name)).read()


def e(x):
    return 10.0 ** (0.1 * x)


def db(x):
    return 10.0 * math.log10(x)


def band_row(doc, label):
    """the eight numbers of a table row of the documents"""
    m = re.search(r"^\| %s[^|]*\|(.+)\|\s*$" % re.escape(label), doc, re.M)
    return [float(x) for x in m.group(1).split("|")]


def certificates(doc):
    """{instrument: {band: correction to add to its indication}}, from the certificate table"""
    out = {}
    for name, cells in re.findall(r"^\| (M-\d+) \([^)]*\) \|(.+)\|\s*$", doc, re.M):
        out[name] = dict(zip(LABEL, [float(x) for x in cells.split("|")]))
    return out


def load(data):
    std = text(data, "docs/standard.md")
    C = dict(
        clear=float(re.search(r"standing ([\d.]+) m or more from every wall", std).group(1)),
        margin=float(re.search(r"by less than (\d+) dB in any band", std).group(1)),
        minpos=int(re.search(r"At least (\d+) valid positions", std).group(1)),
        sabine=float(re.search(r"A = ([\d.]+) V / T", std).group(1)),
        speed=float(re.search(r"(\d+) lg \(n_rated / n\)", std).group(1)),
        aw=dict(zip(LABEL, band_row(std, "Aw (dB)"))),
    )
    room = text(data, "docs/room_report.md")
    C["V"] = float(re.search(r"a volume of (\d+) m3", room).group(1))
    C["cert"] = certificates(text(data, "docs/meter_certificates.md"))
    check = text(data, "docs/room_check.md")
    C["rss_lw"] = dict(zip(LABEL, band_row(check, "Lw (dB)")))
    C["rss_r"] = float(re.search(r"hemisphere of ([\d.]+) m", check).group(1))
    M = {}
    for r in rows(data, "machines.csv"):
        M[r["machine"]] = dict(rated=float(r["rated_speed_rpm"]), nominal_r=float(r["nominal_survey_radius_m"]),
                               wall=float(r["wall_clearance_m"]), guarantee=float(r["guaranteed_lwa_db"]),
                               pos=[], survey={}, speed=None, certified=None)
        # a note against a machine may carry the certified insertion loss of what was fitted to it, which the
        # standard allows in place of a measured difference
        m = re.search(r"certified insertion loss by octave band ([\d./]+) dB", r["note"])
        if m:
            M[r["machine"]]["certified"] = dict(zip(LABEL, [-float(x) for x in m.group(1).split("/")]))
    # the position table is the authority on which array a position belongs to: the survey sheet's own machine
    # column disagrees with it on four rows, and a row's levels are the levels of the pass that visited it
    P = {}
    for r in rows(data, "positions.csv"):
        P[r["position"]] = dict(machine=r["machine"], r=float(r["radius_m"]))
        M[r["machine"]]["pos"].append(r["position"])
    for r in rows(data, "survey_levels.csv"):
        pid = r["position"]
        m = P[pid]["machine"]
        P[pid]["meter"] = r["meter"]
        M[m]["survey"][pid] = {k: float(r["lp_%s" % k]) for k in LABEL}
        M[m]["speed"] = float(r["speed_rpm"])
    BG = {}
    for r in rows(data, "background_levels.csv"):
        BG[r["position"]] = {k: float(r["lp_%s" % k]) for k in LABEL}
        BG[r["position"]]["meter"] = r["meter"]
    RSS = {}
    for r in rows(data, "rss_levels.csv"):
        RSS[r["position"]] = {k: float(r["lp_%s" % k]) for k in LABEL}
        P[r["position"]] = dict(machine="RSS", r=C["rss_r"], meter=r["meter"])
    C["rss"] = RSS
    # the machines the log shows were changed after the survey: work that altered what is fitted to the machine,
    # not the consumables (filter panels, oil, elements, traps, grease) or readings taken
    log = rows(data, "maintenance_log.csv")
    survey_date = min(r["date"] for r in log if "acceptance survey" in r["entry"].lower())
    changed = {r["machine"] for r in log if r["machine"] and r["date"] > survey_date
               and re.search(r"\b(fitted|refitted|installed|removed)\b", r["entry"])}
    return C, M, P, BG, changed


class Model:
    def __init__(self, C, M, P, BG, changed, t60=None):
        self.C, self.M, self.P, self.BG, self.changed, self.t60 = C, M, P, BG, changed, t60 or {}
        self.delta = {}

    def array_radius(self, m):
        """the radius the array was set at: the one most of its positions share"""
        rs = [self.P[p]["r"] for p in self.M[m]["pos"]]
        return max(set(rs), key=rs.count)

    def surface(self, m):
        r = self.array_radius(m)
        half = self.M[m]["wall"] >= self.C["clear"]
        return (2.0 * math.pi if half else math.pi) * r * r

    def corrected(self, level, pid):
        """a level as indicated at the position, with the certificate of the instrument that read it added"""
        c = self.C["cert"][self.P[pid]["meter"]]
        return {k: level[k] + c[k] for k in LABEL}

    def machine_only(self, m, p):
        """the level of the machine alone at the position, the background subtracted in energy"""
        on, off = self.corrected(self.M[m]["survey"][p], p), self.corrected(self.BG[p], p)
        return {k: db(max(e(on[k]) - e(off[k]), 1e-12)) for k in LABEL}

    def valid(self, m):
        out = []
        for p in self.M[m]["pos"]:
            if abs(self.P[p]["r"] - self.array_radius(m)) > 1e-9:
                continue
            on, off = self.corrected(self.M[m]["survey"][p], p), self.corrected(self.BG[p], p)
            if min(on[k] - off[k] for k in LABEL) < self.C["margin"]:
                continue
            out.append(p)
        return out

    def absorption(self):
        """the hall's equivalent absorption area band by band, from the room check of the survey: the reference
        source's own level on its hemisphere, with the hall's background taken off, against its certified sound
        power. The level away from the louvred wall is the background of any of the machines' positions."""
        rss = self.C["rss"]
        bg = next(p for p in self.BG if p not in getattr(self, "near_wall", ()))
        off = self.corrected(self.BG[bg], bg)
        s = 2.0 * math.pi * self.C["rss_r"] ** 2
        out = {}
        for k in LABEL:
            vals = [db(max(e(self.corrected(rss[p], p)[k]) - e(off[k]), 1e-12)) for p in rss]
            lp = db(sum(e(v) for v in vals) / len(vals))
            out[k] = 4.0 / (e(lp - self.C["rss_lw"][k]) - 1.0 / s)
        return out

    def area(self, k):
        if self.t60:
            return self.C["sabine"] * self.C["V"] / self.t60[k]
        if not getattr(self, "_abs", None):
            self._abs = self.absorption()
        return self._abs[k]

    def k2(self, m, k):
        s = self.surface(m)
        return db(1.0 + 4.0 * s / self.area(k))

    def lw(self, m):
        pos = self.valid(m)
        s = self.surface(m)
        out = {}
        for k in LABEL:
            lp = db(sum(e(self.machine_only(m, p)[k]) for p in pos) / len(pos))
            out[k] = lp + db(s) - self.k2(m, k)
        if self.M[m]["speed"] != self.M[m]["rated"]:
            r = self.C["speed"] * math.log10(self.M[m]["rated"] / self.M[m]["speed"])
            out = {k: v + r for k, v in out.items()}
        if m in self.delta:
            out = {k: v + self.delta[m][k] for k, v in out.items()}
        return out

    def lwa(self, lw):
        return db(sum(e(lw[k] + self.C["aw"][k]) for k in LABEL))


def reading(*args):
    out = subprocess.run(list(args), capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.startswith(("level_dB", "T_s")):
            return dict(zip(LABEL, [float(x) for x in line.split(",")[1:]]))
    raise RuntimeError(out)


def main(data, out):
    C, M, P, BG, changed = load(data)
    A = Model(C, M, P, BG, changed)
    # the configuration difference of every machine the log shows was changed after the survey and whose survey
    # pass was at its rated speed, measured at the first valid position of its own array
    for m in sorted(changed):
        if M[m]["speed"] != M[m]["rated"]:
            continue
        if M[m]["certified"]:
            A.delta[m] = M[m]["certified"]
            continue
        p = A.valid(m)[0]
        now = reading("slm", p, m.lower())
        then = A.machine_only(m, p)
        A.delta[m] = {k: db(max(e(now[k]) - e(A.corrected(BG[p], p)[k]), 1e-12)) - then[k] for k in LABEL}
    sheet = {m: A.lw(m) for m in M}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as f:
        f.write("machine,%s,lwa\n" % ",".join("lw_%s" % k for k in LABEL))
        for m in sorted(sheet):
            f.write("%s,%s,%.1f\n" % (m, ",".join("%.1f" % sheet[m][k] for k in LABEL), A.lwa(sheet[m])))
    print("equivalent absorption area from the room check: %s m2" % " ".join(
        "%.1f" % A.area(k) for k in LABEL))
    for m in sorted(sheet):
        print("%s: %d valid positions, surface %.2f m2, K2 %s" % (
            m, len(A.valid(m)), A.surface(m), " ".join("%.2f" % A.k2(m, k) for k in LABEL)))
        if m in A.delta:
            print("     configuration difference %s dB" % " ".join("%+.2f" % A.delta[m][k] for k in LABEL))
        if M[m]["speed"] != M[m]["rated"]:
            print("     referred from %.0f to %.0f rpm: %+.2f dB" % (
                M[m]["speed"], M[m]["rated"], C["speed"] * math.log10(M[m]["rated"] / M[m]["speed"])))
        print("     Lw %s  LwA %.1f (guarantee %.0f)" % (
            " ".join("%.1f" % sheet[m][k] for k in LABEL), A.lwa(sheet[m]), M[m]["guarantee"]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/app/data",
         sys.argv[2] if len(sys.argv) > 2 else "/app/output/sound_power.csv")
