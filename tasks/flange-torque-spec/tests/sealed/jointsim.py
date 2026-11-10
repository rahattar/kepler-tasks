"""Sealed definition for flange-torque-spec. Nothing in the agent's documents names the effects below; they are
recoverable only from the physics and from fine details of the records.

Sixteen zinc-plated flanged joints. Per-bolt preload from a single-bolt tightening: F = T / (K d) while elastic; if
that exceeds the bolt's proof load the bolt yields and the preload is clipped near proof (the rig reports it as an
ordinary number). K (nut factor) is set by thread friction: flank roughness, plating thickness (the zinc galls once the
coating is thicker than the 6g thread's coating allowance |es|/4: 9.5 um on M16, 10.5 on M20, 12.0 on M24), reused
threads (friction rises with each earlier assembly, steeply at first and then levelling off), plus small per-joint scatter.

In the assembled joint, tightening the full bolt pattern relaxes every bolt by an elastic-interaction fraction set by
the flange design and by the tightening sequence. For the crew's sequence (one cross-pattern pass at the full torque,
procedure.md) the fraction is r = C_INT * d / (s * t), with d the bolt diameter, s = pi * PCD / n the bolt spacing
and t the flange thickness (all mm). The two example assemblies were tightened in incremental cross-pattern passes
followed by two circular check passes (stated in each record); the check passes recover part of the loss, and the
fraction that remains is M_REC * r. So the records' ratio of assembled to single-bolt preload is 1 - M_REC r, while
the crew's is 1 - r. The requirement is on the ASSEMBLED per-bolt preload under the crew's sequence; a single-bolt
trial reports the single-bolt preload, a pattern trial (crew's sequence, costs two trials) reports the assembled
preload of a monitored bolt.
"""
import numpy as np

K_HB = 0.18
K0, B_RA, B_TP, REUSE_SAT, REUSE_N0, EPS_SIGMA = 0.146, 0.030, 0.020, 0.050, 1.2, 0.0025
# zinc-plated threads gain friction with every tightening, steeply over the first few and then levelling off:
# REUSE_SAT (1 - exp(-n / REUSE_N0)) for n earlier assemblies (JOINTS field 8 counts them)
# zinc galls under the nut once the coating is thicker than the 6g thread can take: the coating allowance is |es|/4,
# with es the fundamental deviation of the 6g external thread (ISO 965-1; ISO 4042)
ES_6G_UM = {12: -34.0, 16: -38.0, 20: -42.0, 24: -48.0}
COAT_MAX_UM = {d: abs(es) / 4.0 for d, es in ES_6G_UM.items()}
WINDOW = 0.06
GATE = 15
BUDGET = 8

STRESS_AREA = {12: 84.3, 16: 157.0, 20: 245.0, 24: 353.0}        # mm2 (coarse thread)
PROOF_STRESS = {"8.8": 600.0, "10.9": 830.0}                      # MPa
# elastic interaction: assembled preload = single-bolt preload * (1 - r), r = C_INT d / (s t)
C_INT = 11.6
M_REC = 0.3       # fraction of the loss left by the example records' sequence (two check passes)
PATTERN_COST = 2  # a pattern trial uses two of the trial budget
FLANGE_T_MM = {"A": 22.0, "B": 28.0}  # flange thickness by class, printed in the schedule
# bolt circle diameter (mm) by flange design (class, bolt count, bolt size)
PCD_MM = {("A", 12, 16): 230.0, ("B", 8, 20): 280.0, ("B", 6, 24): 300.0}


def pcd_of(jid, fc, n, d_mm):
    return PCD_MM[(fc, n, d_mm)]


def interaction(fc, n, d_mm, pcd):
    s = np.pi * pcd / n
    return C_INT * d_mm / (s * FLANGE_T_MM[fc])

# (id, d_mm, grade, n_bolts, flange_class, Ra_um, tp_um, reused, target_frac_of_proof)
JOINTS = [
    ("J01", 16, "8.8", 12, "A", 1.1, 6.0, 0, 0.70),
    ("J02", 20, "8.8", 8, "B", 2.9, 7.5, 0, 0.68),
    ("J03", 16, "10.9", 12, "A", 1.8, 7.5, 0, 0.66),
    ("J04", 20, "8.8", 8, "B", 2.2, 8.0, 1, 0.70),
    ("J05", 24, "10.9", 6, "B", 0.9, 15.0, 0, 0.72),
    ("J06", 16, "8.8", 12, "A", 3.1, 6.5, 0, 0.66),
    ("J07", 16, "8.8", 12, "A", 2.4, 6.5, 0, 0.64),
    ("J08", 20, "10.9", 8, "B", 2.6, 7.0, 3, 0.70),
    ("J09", 16, "8.8", 12, "A", 1.5, 12.0, 0, 0.70),
    ("J10", 24, "8.8", 6, "B", 1.3, 10.5, 2, 0.70),
    ("J11", 16, "10.9", 12, "A", 2.4, 8.5, 2, 0.68),
    ("J12", 20, "8.8", 8, "B", 1.7, 13.5, 0, 0.72),
    ("J13", 16, "8.8", 12, "A", 2.0, 8.0, 1, 0.64),
    ("J14", 16, "8.8", 12, "A", 2.8, 7.0, 4, 0.66),
    ("J15", 24, "8.8", 6, "B", 2.1, 6.0, 0, 0.70),
    ("J16", 20, "10.9", 8, "B", 1.0, 8.0, 0, 0.72),
]
# two past assemblies (examples), one per flange class, with trial and assembled preload recorded
EXAMPLES = [("E01", 16, "8.8", 12, "A", 2.3, 7.0, 0, 0.70), ("E02", 20, "8.8", 8, "B", 1.9, 6.5, 0, 0.70)]


def proof_load_N(d, grade):
    return STRESS_AREA[d] * PROOF_STRESS[grade]


def k_model(Ra, tp, reused, d_mm):
    return K0 + B_RA * (Ra - 2.0) + B_TP * max(0.0, tp - COAT_MAX_UM[d_mm]) + REUSE_SAT * (1.0 - np.exp(-reused / REUSE_N0))


def seal(seed=4315):
    rng = np.random.default_rng(seed)
    truth = {}
    for (jid, d, grade, n, fc, Ra, tp, reused, frac) in JOINTS + EXAMPLES:
        k = k_model(Ra, tp, reused, d) + rng.normal(0, EPS_SIGMA)
        Fp = proof_load_N(d, grade)
        truth[jid] = dict(k_true=float(k), d=d * 1e-3, d_mm=d, grade=grade, n=n, fc=fc, Ra=Ra, tp=tp,
                          reused=reused, Fproof=Fp, Ftarget=frac * Fp, r=float(interaction(fc, n, d, pcd_of(jid, fc, n, d))),
                          pcd=pcd_of(jid, fc, n, d))
    return truth


def single_bolt(t, torque):
    """single-bolt preload at torque; clipped near proof if the bolt yields (returns F, yielded)"""
    Fel = torque / (t["k_true"] * t["d"])
    if Fel > t["Fproof"]:
        return t["Fproof"] * (1.0 + 0.03 * np.tanh((Fel / t["Fproof"] - 1.0) * 3.0)), True
    return Fel, False


def trial(truth, jid, rng, torque=None, pattern=False):
    """single-bolt trial: preload in the one bolt tightened. pattern trial: every bolt of the pattern tightened to the
    torque in the rig's sequence, then the preload of a monitored bolt (assembled preload)."""
    t = truth[jid]
    if torque is None:
        torque = K_HB * t["d"] * t["Ftarget"]          # the rig's default: handbook K at the joint's target
    F, _ = single_bolt(t, torque)
    if pattern:
        F = F * (1.0 - t["r"])
    return float(torque), float(F * (1 + rng.normal(0, 0.010)))


def grade(truth, torques):
    res, npass = {}, 0
    for jid, t in truth.items():
        if jid.startswith("E"):
            continue
        T = torques.get(jid)
        if T is None or not np.isfinite(T):
            res[jid] = dict(ok=False, reason="no torque"); continue
        Fs, yielded = single_bolt(t, T)
        Fa = Fs * (1.0 - t["r"])
        e = Fa / t["Ftarget"] - 1
        ok = (abs(e) <= WINDOW) and not yielded
        npass += ok
        res[jid] = dict(ok=bool(ok), err_pct=round(100 * e, 2), yielded=bool(yielded))
    return dict(npass=npass, gate=GATE, accepted=npass >= GATE, joints=res)
