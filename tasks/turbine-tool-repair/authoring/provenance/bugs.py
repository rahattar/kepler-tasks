"""The shipped program is the correct reduction with these edits applied (each is one defect). make(bugs) returns the
program text with the chosen defects; make(ALL) is the plant's program as shipped."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BUGS = {
    "pf_sign": ("power factor correction applied with the wrong sign",
                "p_pf = P + gen_loss_kw(P, pf) - gen_loss_kw(P, REF_PF)",
                "p_pf = P + gen_loss_kw(P, REF_PF) - gen_loss_kw(P, pf)"),
    "hr_multiply": ("heat rate multiplied by its correction factors instead of divided",
                    "3600.0 * heat / p_pf / g))", "3600.0 * heat / p_pf * g))"),
    "ethane_value": ("ethane heating value mistyped (1482.84 for 1428.84 kJ/mol)",
                     '"C2H6": (1428.84, 30.069)', '"C2H6": (1482.84, 30.069)'),
    "cit_table_typo": ("CIT output factor at 25 degC mistyped (0.9425 for 0.9245)",
                       "[25, 0.9245, 1.0230]", "[25, 0.9425, 1.0230]"),
    "clamped_curves": ("curves held at the end values outside the tables instead of extrapolated",
                       """    y = np.where(x < xs[0], ys[0] + (x - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0]), y)
    y = np.where(x > xs[-1], ys[-1] + (x - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2]), y)
""", ""),
    "fuel_temp_meter": ("fuel sensible heat from the meter temperature TE-301 instead of TE-305",
                        "(a.te305_fuel_skid_c - 15.0)", "(a.te301_fuel_meter_c - 15.0)"),
    "heat_parentheses": ("fuel sensible heat not multiplied by the fuel flow (parentheses lost)",
                         "heat = a.m_fuel * (lhv + CP_FUEL * (", "heat = a.m_fuel * lhv + CP_FUEL * ("),
    "exhaust_columns": ("exhaust loss table with its output and heat rate columns exchanged",
                        """EXHAUST_TABLE = np.array([
    [0.0, 1.0165, 0.9850], [1.0, 1.0110, 0.9900], [2.0, 1.0055, 0.9950], [3.0, 1.0000, 1.0000],
    [4.0, 0.9945, 1.0050], [5.0, 0.9890, 1.0100], [6.0, 0.9835, 1.0150]])""",
                        """EXHAUST_TABLE = np.array([
    [0.0, 0.9850, 1.0165], [1.0, 0.9900, 1.0110], [2.0, 0.9950, 1.0055], [3.0, 1.0000, 1.0000],
    [4.0, 1.0050, 0.9945], [5.0, 1.0100, 0.9890], [6.0, 1.0150, 0.9835]])"""),
    "inlet_loss_filter": ("inlet pressure loss taken from the filter differential pressure only",
                          'd["dp_in"] = d.p_amb - d.pt102_inlet_total_kpa_abs', 'd["dp_in"] = d.pdt101_filter_dp_kpa'),
    "gas_components": ("hydrogen, helium and neo-pentane missing from the component table, extra columns ignored",
                       """    "nC4H10": (2657.60, 58.122), "neoC5H12": (3250.48, 72.149), "iC5H12": (3265.08, 72.149),
    "nC5H12": (3272.00, 72.149), "nC6H14": (3887.21, 86.175), "H2": (241.72, 2.016), "He": (0.0, 4.0026),
    "N2": (0.0, 28.0135), "CO2": (0.0, 44.010), "O2": (0.0, 31.9988),""",
                       """    "nC4H10": (2657.60, 58.122), "iC5H12": (3265.08, 72.149), "nC5H12": (3272.00, 72.149),
    "nC6H14": (3887.21, 86.175), "N2": (0.0, 28.0135), "CO2": (0.0, 44.010), "O2": (0.0, 31.9988),"""),
    "baro_units": ("barometer read only from met_baro_hpa",
                   """    if "met_baro_kpa" in d:
        d["p_amb"] = d["met_baro_kpa"]
    else:
        d["p_amb"] = d["met_baro_hpa"] / 10.0""", """    d["p_amb"] = d["met_baro_hpa"] / 10.0"""),
    "fuel_units": ("fuel flow read only from fuel_coriolis_kg_s",
                   """    if "fuel_coriolis_kg_s" in d:
        d["m_fuel"] = d["fuel_coriolis_kg_s"]
    else:
        d["m_fuel"] = d["fuel_coriolis_kg_h"] / 3600.0""", """    d["m_fuel"] = d["fuel_coriolis_kg_s"]"""),
    "failed_rtd": ("a failed RTD channel (-999.0) averaged into CIT",
                   """d[["cit_%d_c" % i for i in range(1, 9)]].where(lambda v: v > FAILED + 1.0)""",
                   """d[["cit_%d_c" % i for i in range(1, 9)]]"""),
    "aborted_runs": ("an aborted run treated as ended",
                     """            out.setdefault(words[1], {})[words[2]] = r.time
    return {k: v for k, v in out.items() if "start" in v and "end" in v and "aborted" not in v}""",
                     """            out.setdefault(words[1], {})["end" if words[2] == "aborted" else words[2]] = r.time
    return {k: v for k, v in out.items() if "start" in v and "end" in v}"""),
    "texh_one_sided": ("exhaust temperature test one-sided: minutes far below the control reference pass as base load",
                       "((x.texh_avg_c - x.ttrf_c).abs() <= TEXH_BAND)", "((x.texh_avg_c - x.ttrf_c) <= TEXH_BAND)"),
    "gas_any_day": ("LHV averaged over every sample in the file, not only the test day's",
                    """    day = d.index[0].normalize()
    same_day = pd.to_datetime(gas.sample_time).dt.normalize() == day
    lhv = float(np.mean([lhv_kj_kg(r) for _, r in gas[same_day].iterrows()]))""",
                    """    lhv = float(np.mean([lhv_kj_kg(r) for _, r in gas.iterrows()]))"""),
    "frozen_rtd": ("an RTD frozen at one reading (not flagged -999 by the DAS) kept in the CIT mean",
                   """    rtd = rtd.loc[:, rtd.std() > FROZEN]          # a transmitter frozen at one reading is not in service
""", ""),
    "rest_rtd": ("inlet RTDs not checked against the met dry bulb at rest (rev 4 instrument verification)",
                 """        rtd = rtd - (rtd[rest].sub(d.met_dry_bulb_c[rest], axis=0)).median()
""", ""),
    "rest_pt102": ("PT-102 not checked against the barometer at rest (rev 4 instrument verification)",
                   """        d["pt102_inlet_total_kpa_abs"] = d.pt102_inlet_total_kpa_abs - (d.pt102_inlet_total_kpa_abs - d.p_amb)[rest].median()
""", ""),
    "rest_fuel": ("FT-301 zero not checked at rest (rev 4 instrument verification)",
                  """        d["m_fuel"] = d.m_fuel - d.m_fuel[rest].median()
""", ""),
}
ALL = list(BUGS)
REST_BLOCK = """    rest = d.speed_pct < AT_REST                 # on the turning gear: no air flow, no fuel flow
    if rest.any():
"""
REST_CONST = "AT_REST = 1.0                                    # % speed; the turning gear holds the rotor at about 0.2 %\n"
UNKNOWN_CHECK = """    unknown = [c for c in sample.index if c not in COMPONENTS and c not in ("sample_time", "gross_cv_mj_m3_15_15")]
    if unknown:
        raise ValueError("gas analysis has components not in the procedure table: %s" % unknown)
"""


def make(bugs, ref=os.path.join(HERE, "..", "..", "solution", "gtperf.py")):
    s = open(ref).read()
    for b in bugs:
        _, old, new = BUGS[b]
        assert s.count(old) == 1, (b, s.count(old))
        s = s.replace(old, new)
    if "heat_parentheses" in bugs:
        import re
        s = re.sub(r"(heat = a\.m_fuel \* lhv \+ CP_FUEL \* \(a\.te30[15]_fuel_[a-z]+_c - 15\.0\))\)", r"\1", s)
    if "gas_components" in bugs:
        s = s.replace(UNKNOWN_CHECK, "")
    if "failed_rtd" in bugs:
        s = s.replace("FAILED = -999.0                                  # a failed RTD channel\n", "")
    if "frozen_rtd" in bugs:
        s = s.replace("FROZEN = 0.01                                    # K; a live RTD's readings vary by more than this over a day\n", "")
    if {"rest_rtd", "rest_pt102", "rest_fuel"} <= set(bugs):
        assert s.count(REST_BLOCK) == 1 and s.count(REST_CONST) == 1
        s = s.replace(REST_BLOCK, "").replace(REST_CONST, "")
    if set(bugs) == set(ALL):
        s = s.replace('"""GT-1 performance test reduction (plant procedure TP-GT-07 rev 4).',
                      '"""GT-1 performance test reduction - plant program v2.3 (2021, written to TP-GT-07 rev 3).')
    return s
