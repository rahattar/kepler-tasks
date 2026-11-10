"""Correct methods on the shipped scenario: the reference and variants that differ in order, fits, constants, the
rule that picks the setpoint and where the tests are made, and the independent solution.

    python3 authoring/evidence/method_spread.py      (writes method_spread.txt)
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import independent  # noqa: E402
import solve  # noqa: E402

REF = C.REF_PLAN


class LabAtSetpoint(solve.Model):
    """tests at the production setpoint itself; the model still converts time"""
    def lab_temperature(self, b, Tp, double):
        return int(Tp)


class Coupon(solve.Model):
    """every test on the laboratory's default 25 mm round at half-radius; the section rule carries it to the batch"""
    def test_piece(self, D, loc):
        return 25.0, "half-radius"


VARIANTS = [
    ("reference", dict(plan=REF)),
    ("reference tests in reverse order (other scatter draws)", dict(plan=REF[::-1])),
    ("reference tests, PCHIP through the supplier points", dict(plan=REF, model_kw=dict(interp="pchip"))),
    ("reference tests, Hollomon-Jaffe constant 19", dict(plan=REF, model_kw=dict(c_hj=19.0))),
    ("reference tests, Hollomon-Jaffe constant 21", dict(plan=REF, model_kw=dict(c_hj=21.0))),
    ("reference tests, setpoint solved for the middle of the range", dict(plan=REF, model_kw=dict(rule="mid"))),
    ("laboratory temperatures 10 C below the equivalent", dict(plan=REF, lab_dT=-10)),
    ("laboratory temperatures 10 C above the equivalent", dict(plan=REF, lab_dT=10)),
    ("tests at the production setpoint itself", dict(plan=REF, model_cls=LabAtSetpoint)),
    ("tests on 25 mm half-radius pieces", dict(plan=REF, model_cls=Coupon)),
    ("52-1250 tested at B07 instead of B11", dict(plan=[("B07", True)] + REF[1:])),
    ("52-1312 tested at B08 instead of B06", dict(plan=[REF[0], ("B08", True)] + REF[2:])),
    ("52-1250 at B07 and B11; 32-0458 and 43-2210 left to the supplier curves",
     dict(plan=[("B07", True), ("B11", True), ("B06", True), ("B13", True), ("B09", False), ("B12", False)])),
    ("41-7864 also at B02 in place of 43-2210", dict(plan=REF[:-1] + [("B02", False)])),
]


def main():
    out = []
    for name, kw in VARIANTS:
        temps, lab = C.run(**kw)
        n, worst, m, bad = C.summary(temps)
        out.append("%-76s %2d of 13  tempers %2d  smallest true margin %+.2f HRC (%s)%s" % (
            name, n, lab.used, m, worst, ("  fails " + " ".join(bad)) if bad else ""))
    temps, n, txt = independent.main()
    worst = min(temps, key=lambda b: C.margin(b, temps[b]))
    out.append("%-76s %2d of 13  tempers 10  smallest true margin %+.2f HRC (%s)" % (
        "independent solution (other tests, fits and rule; independent.txt)", n, C.margin(worst, temps[worst]), worst))
    return "\n".join(out)


if __name__ == "__main__":
    txt = main()
    print(txt)
    open(os.path.join(HERE, "method_spread.txt"), "w").write(txt + "\n")
