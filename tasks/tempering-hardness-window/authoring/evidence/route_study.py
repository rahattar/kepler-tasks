"""Defective and alternative routes on the shipped scenario: each departs from the reference in one way.

    python3 authoring/evidence/route_study.py      (writes route_study.txt)

Every route uses the reference's machinery (common.run) with one part replaced, the same laboratory (allowance 10
tempers, the real laboratory's readings) and the same setpoint rule. The matrix at the end shows, batch by batch,
which routes get which batches right.
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import solve  # noqa: E402

S = C.S
REF = C.REF_PLAN
OTHERS = [("B09", False), ("B12", False), ("B05", False), ("B03", False)]


def undo_log(rec):
    rec.batches["B09"]["heat"] = "41-7731"


class NoSoak(solve.Model):
    def predict(self, b, T):
        r = self.rec.batches[b]
        heat, D, loc = r["heat"], float(r["ruling_section_diameter_mm"]), r["hardness_location"]
        off = self.boff.get(b, self.offset.get(heat, 0.0))
        return self.raw(heat, T, D, loc, 2.0 * self.rec.ntemper(heat)) + off

    def lab_temperature(self, b, Tp, double):
        return int(Tp)


class NoDouble(solve.Model):
    """production taken as one soak for every grade"""
    def predict(self, b, T):
        r = self.rec.batches[b]
        heat, D, loc = r["heat"], float(r["ruling_section_diameter_mm"]), r["hardness_location"]
        off = self.boff.get(b, self.offset.get(heat, 0.0))
        return self.raw(heat, T, D, loc, self.rec.soak(D)) + off

    def lab_temperature(self, b, Tp, double):
        r = self.rec.batches[b]
        D = float(r["ruling_section_diameter_mm"])
        target = self.teq(Tp, self.rec.soak(D))
        lo, hi = 300.0, 800.0
        for _ in range(60):
            m = 0.5 * (lo + hi)
            lo, hi = (m, hi) if self.teq(m, 2.0) < target else (lo, m)
        return int(round(0.5 * (lo + hi)))


class NoSection(solve.Model):
    """no section effect, and test pieces of the laboratory's default 25 mm round at half-radius"""
    def raw(self, heat, T, D, loc, hours_total):
        return self.sup(self.rec.grade(heat), self.teq(T, hours_total))

    def test_piece(self, D, loc):
        return 25.0, "half-radius"


def as_heat(untested, like):
    """an untested heat taken to behave like another heat's tests (or, like=None, like the supplier curve)"""
    def after(model, tests):
        for b, r in model.rec.batches.items():
            if r["heat"] == untested:
                model.boff.pop(b, None)
                if like is None:
                    model.offset[untested] = 0.0
                else:
                    model.offset[untested] = model.offset[like]
    return after


def g52_single_plan():
    return [("B11", False), ("B06", False), ("B13", False)] + OTHERS + [("B02", False), ("B01", False), ("B07", False)]


def pair_corrected(model, tests):
    """single tests on G52, corrected by the single-minus-double difference of one pair on 52-1312 (B06)"""
    single = [h - model.raw(he, Tl, D, loc, 2.0) for he, b, Tl, D, loc, d, h in tests if he == "52-1312" and not d]
    double = [h - model.raw(he, Tl, D, loc, 4.0) for he, b, Tl, D, loc, d, h in tests if he == "52-1312" and d]
    corr = single[0] - double[0]
    for he, b, Tl, D, loc, d, h in tests:
        if model.rec.grade(he) == "G52" and not d and he != "52-1312":
            model.boff[b] = model.offset[he] = h - model.raw(he, Tl, D, loc, 2.0) - corr
    for b, r in model.rec.batches.items():
        if r["heat"] == "52-1312":
            model.boff[b] = model.offset["52-1312"] = double[0]


FREE2 = [("B02", False), ("B01", False)]
ROUTES = [
    ("reference", dict(plan=REF)),
    ("production log missed (B09 as 41-7731, tested as such)", dict(plan=REF, rec_fn=undo_log)),
    ("no tests: supplier curves with every conversion", dict(plan=[])),
    ("soak time ignored (2 h tempers at the setpoint)", dict(plan=REF, model_cls=NoSoak)),
    ("G52 double tempering ignored (one soak; G52 tested once)",
     dict(plan=[("B11", False), ("B06", False), ("B13", False)] + OTHERS + [("B02", False), ("B01", False), ("B07", False)],
          model_cls=NoDouble)),
    ("section ignored (25 mm half-radius test pieces)", dict(plan=REF, model_cls=NoSection)),
    ("G52 tested once at the Hollomon-Jaffe equivalent (double = twice the time)", dict(plan=g52_single_plan())),
    ("G52 tested once, corrected by one single/double pair on 52-1312",
     dict(plan=[("B06", False), ("B06", True), ("B11", False), ("B13", False)] + OTHERS + [("B02", False)],
          after=pair_corrected)),
    ("52-1250 untested, as the supplier curve",
     dict(plan=[("B06", True), ("B13", True)] + OTHERS + FREE2, after=as_heat("52-1250", None))),
    ("52-1250 untested, as 52-1312's test",
     dict(plan=[("B06", True), ("B13", True)] + OTHERS + FREE2, after=as_heat("52-1250", "52-1312"))),
    ("52-1312 untested, as the supplier curve",
     dict(plan=[("B11", True), ("B13", True)] + OTHERS + FREE2, after=as_heat("52-1312", None))),
    ("52-1312 untested, as 52-1250's test",
     dict(plan=[("B11", True), ("B13", True)] + OTHERS + FREE2, after=as_heat("52-1312", "52-1250"))),
    ("52-1377 untested, as the supplier curve",
     dict(plan=[("B11", True), ("B06", True)] + OTHERS + FREE2, after=as_heat("52-1377", None))),
    ("52-1377 untested, as 52-1250's test",
     dict(plan=[("B11", True), ("B06", True)] + OTHERS + FREE2, after=as_heat("52-1377", "52-1250"))),
    ("41-7864 tested only at B02's 150 mm half-radius",
     dict(plan=[(b, d) for b, d in REF if b != "B09"] + [("B02", False)])),
    ("43-2288 untested, as the supplier curve",
     dict(plan=[(b, d) for b, d in REF if b != "B12"] + [("B01", False)], after=as_heat("43-2288", None))),
    ("43-2288 untested, as 43-2210's test",
     dict(plan=[(b, d) for b, d in REF if b != "B12"] + [("B01", False)], after=as_heat("43-2288", "43-2210"))),
]


SEEDS = range(6401, 6421)


def main():
    out, matrix = [], []
    out.append("Shipped scenario (seed %d); the last column counts the scatter seeds 6401-6420 on which the route gets all 13." % C.SEED)
    for name, kw in ROUTES:
        temps, lab = C.run(**kw)
        n, worst, m, bad = C.summary(temps)
        k = sum(C.summary(C.run(seed=sd, **kw)[0])[0] == 13 for sd in SEEDS)
        out.append("%-80s %2d of 13  tempers %2d  worst %s %+.2f HRC%s  [all 13 on %d of 20 seeds]" % (
            name, n, lab.used, worst, m, ("  fails " + " ".join(bad)) if bad else "", k))
        matrix.append((name, {b: C.margin(b, temps[b]) >= 0 for b in S.BATCHES}))
    out.append("")
    out.append("Matrix (routes by batch; + right, . wrong):")
    out.append("%-6s %s" % ("", " ".join(b[1:] for b in S.BATCHES)))
    for i, (name, row) in enumerate(matrix):
        out.append("%-6s %s   %s" % ("R%02d" % i, "  ".join("+" if row[b] else "." for b in S.BATCHES), name))
    failed_by = {b: sum(not row[b] for name, row in matrix) for b in S.BATCHES}
    out.append("routes failing each batch: " + " ".join("%s %d" % (b, k) for b, k in failed_by.items()))
    return "\n".join(out)


if __name__ == "__main__":
    txt = main()
    print(txt)
    open(os.path.join(HERE, "route_study.txt"), "w").write(txt + "\n")
