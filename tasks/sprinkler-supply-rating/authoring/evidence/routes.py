"""Defective routes: the reference audit with one step replaced by a plausible wrong one."""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "solution")))
import rate as R  # noqa: E402


class NoConstants(R.Audit):
    """Everything between the main's static and the residual is taken as flow loss: no opening differentials."""
    def opening(self, tests):
        return [0.0, 0.0], {rid: 0.0 for rid in self.reg if self.reg[rid]["lead_in_check"]}


class StaticsAsRead(R.Audit):
    """Every static is set against the main at that minute, the first of each round included."""
    def usable_statics(self, tests):
        for cur in tests:
            yield cur, self.main.at(cur["t"])


class StaticMinusResidual(R.Audit):
    """The drop of a main drain test is its static less its residual, averaged over every test."""
    def own_series(self, rid, tests, B, h_b, Cv_b, h_c):
        size = self.reg[rid]["lead_in_size_in"]
        rows = []
        for x in tests:
            if x["riser"] != rid:
                continue
            e = self.era(x["t"])
            q = self.drain_k(rid, x["t"]) * math.sqrt(x["resid_gauge"])
            own = x["static"] - x["resid"] - B * (q / 1000.0) ** R.HW - (q / Cv_b[e]) ** 2
            if rid in h_c:
                own -= (q / R.CHECK_CV[size]) ** 2
            rows.append((x["t"], q, own))
        return rows


class SheetBackflow(R.Audit):
    """The backflow preventer at the maker's figures."""
    def opening(self, tests):
        h_b, h_c = super().opening(tests)
        shift = [4.0 - h_b[0], 4.0 - h_b[1]]
        return [4.0, 4.0], {k: v - shift[1] * 0 for k, v in h_c.items()}

    def bfp_cv(self, B, h_b, h_c):
        return [950.0, 950.0]


class OneAssembly(R.Audit):
    """The overhaul is not taken as changing the assembly: one h_b and one Cv_b for the whole record."""
    def era(self, t):
        return 1


class SheetChecks(R.Audit):
    """Lead-in checks at the maker's opening differential."""
    def opening(self, tests):
        h_b, h_c = super().opening(tests)
        return h_b, {k: 1.5 for k in h_c}


class NoCertificates(R.Audit):
    def zero(self, rid, t, logged):
        return 0.0


class LoggedSerial(R.Audit):
    """Each reading corrected by the certificate of the serial written against it in the round's log."""
    def zero(self, rid, t, logged):
        return self.cert[logged] if logged in self.cert else super().zero(rid, t, logged)


class RegisterGaugeOnly(R.Audit):
    """Each riser's readings corrected by the gauge the register shows on it, whenever they were taken."""
    def zero(self, rid, t, logged):
        return self.cert[self.reg[rid]["supply_gauge_serial"]]


class RegisterDrain(R.Audit):
    """The drain pattern of the register throughout."""
    def drain_k(self, rid, t):
        return R.DRAIN_K[self.reg[rid]["main_drain"]]


class MeanC(R.Audit):
    """Cast iron's C as its mean over the record."""
    def cast_iron_C(self, years, C_each):
        return float(np.mean(C_each))


class FittedDuctile(R.Audit):
    """Every lead-in's C fitted from its own record and every control valve taken as fully open."""
    def attribute(self, rid, rows):
        r = dict(self.reg[rid])
        if r["lead_in_material"] != "DI-CL":
            return super().attribute(rid, rows)
        size, L = r["lead_in_size_in"], float(r["lead_in_equiv_length_ft"])
        years = np.array([(t - R.AUDIT).total_seconds() / (365.25 * 86400) for t, _q, _o in rows])
        q = np.array([v for _t, v, _o in rows])
        own = np.array([v for _t, _q, v in rows])
        k = np.maximum(own - (q / R.VALVE_OPEN[size]) ** 2, 1e-3) / q ** R.HW
        C_each = (4.52 * L / (k * R.PIPE_ID[("DI-CL", size)] ** 4.87)) ** (1 / R.HW)
        recent = years > -1.0
        return float(np.mean(C_each[recent])), R.VALVE_OPEN[size]


class SmoothOutlets(R.Audit):
    """Every hydrant outlet at 0.90."""
    def hydrant_flow(self, hydrant, outlets, pitot):
        return int(outlets) * 29.84 * 0.90 * 2.5 ** 2 * math.sqrt(float(pitot))


class OneOutlet(R.Audit):
    """The pitot pressure taken as one outlet's flow, however many were open."""
    def hydrant_flow(self, hydrant, outlets, pitot):
        return 29.84 * R.OUTLET_C[hydrant] * 2.5 ** 2 * math.sqrt(float(pitot))


class TransmitterAtDatum(R.Audit):
    """The utility's record taken as it stands, without the transmitter's depth."""
    def static_main(self, t):
        return self.main.at(t) + R.PSI_FT * R.PIT_BELOW_FT

    def reference_static(self):
        return self.main.reference() + R.PSI_FT * R.PIT_BELOW_FT

    def usable_statics(self, tests):
        for cur, S_high in super().usable_statics(tests):
            yield cur, S_high + R.PSI_FT * R.PIT_BELOW_FT


class GaugesAtDatum(R.Audit):
    def height(self, rid):
        return 0.0


class HoseThroughLeadIn(R.Audit):
    def flows(self, qr):
        return qr + R.HOSE, qr + R.HOSE


class NoHose(R.Audit):
    def flows(self, qr):
        return qr, qr


class AllHoursStatic(R.Audit):
    """The reference static as the quarter's mean over every hour of every day."""
    def reference_static(self):
        v = [s for s, w in zip(self.main.S, self.main.when) if R.REF_FROM <= w.date() <= R.REF_TO]
        return float(np.mean(v))


ROUTES = [NoConstants, StaticsAsRead, StaticMinusResidual, SheetBackflow, OneAssembly, SheetChecks, NoCertificates,
          LoggedSerial, RegisterGaugeOnly, RegisterDrain, MeanC, FittedDuctile, SmoothOutlets, OneOutlet,
          TransmitterAtDatum, GaugesAtDatum, HoseThroughLeadIn, NoHose, AllHoursStatic]
