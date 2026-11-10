"""Sealed definitions of the fans: the fan as built (the OEM datasheet), the events since (impeller re-bladed or
replaced, coupling hub replaced, shaft replaced to a new revision, pedestals regrouted; `date` is the date of the work
and `entered` the date of the asset register entry), the standstill impact tests (date and condition: '' as
installed, 'brace' with the fan-end pedestal's horizontal stay removed), the true pedestal stiffnesses and the new
impeller.

The truth of a fan is the two lowest critical speeds of the fan as it will run: every event applied, the pedestal
stiffnesses after the last support event, and the new impeller (rotor.criticals). The impact tests' frequencies are
the lowest standstill frequencies of the fan as it stood on the test date, rounded to 0.01 Hz as reported."""
import copy
import numpy as np
import rotor as Rt


def shaft(L, b1, b2, d_mid, d_jr, d_oh, d_cpl):
    return [[0.0, b1 - 0.10, d_cpl], [b1 - 0.10, b1 + 0.10, d_jr], [b1 + 0.10, b2 - 0.10, d_mid],
            [b2 - 0.10, b2 + 0.10, d_jr], [b2 + 0.10, L, d_oh]]


def imp(m, rg, wfac=0.55):
    """Impeller (mass, Id about the CG, Ip) from its mass and polar radius of gyration."""
    Ip = m * rg ** 2
    return (float(m), round(wfac * Ip, 1), round(Ip, 1))


def fan(name, seed, oh, d, kH, ratio, m0, rg0, new, rpm, events=(), tests=(("2024-05-14", ""),), mp=200.0, kb=9e8,
        span=1.2, hub=(24.0, 0.35, 0.6)):
    b1 = 0.40; b2 = b1 + span; L = b2 + oh
    return dict(name=name, seed=seed, L=L, bearings=[b1, b2], shaft0=shaft(L, b1, b2, d, d - 0.02, d - 0.03, 0.10),
                hub=hub, imp0=imp(m0, rg0), kH0=kH, kV0=kH * ratio, kb=kb, mp=mp, new=new, rpm=rpm,
                events=[dict(e) for e in events], tests=[dict(date=t, cond=c) for t, c in tests])


EXAMPLE = "boiler-fd-fan"
FANS = [
    fan("boiler-fd-fan", 11, 0.55, 0.150, 3.0e7, 3.5, 420, 0.44, imp(470, 0.47), 1490, span=1.20, mp=200, kb=9.0e8,
        events=[dict(date="2019-06-18", entered="2019-07-02", kind="hub", hub=(31.0, 0.48, 0.82), text="hub")]),
    fan("kiln-id-fan", 21, 0.60, 0.145, 2.5e7, 4.0, 480, 0.46, imp(560, 0.47), 990, span=1.40, mp=280, kb=1.1e9,
        events=[dict(date="2021-08-16", entered="2021-10-04", kind="impeller", imp=imp(550, 0.45), text="re-bladed")],
        tests=[("2021-09-07", "")]),
    fan("raw-mill-fan", 22, 0.45, 0.160, 4.0e7, 4.0, 550, 0.42, imp(500, 0.48), 1180, span=1.10, mp=160, kb=8.0e8,
        events=[dict(date="2024-06-03", entered="2024-06-20", kind="shaft", seg=4, d=0.145, text="overhang")],
        tests=[("2022-10-18", "")]),
    fan("dryer-exhaust-fan", 23, 0.62, 0.155, 2.2e7, 4.5, 400, 0.45, imp(520, 0.50), 1480, span=1.25, mp=220, kb=9.5e8,
        tests=[("2020-04-02", ""), ("2025-01-21", "brace")]),
    fan("coal-mill-fan", 24, 0.50, 0.155, 3.5e7, 3.0, 450, 0.43, imp(380, 0.46), 1185, span=1.30, mp=300, kb=1.2e9,
        events=[dict(date="2021-03-09", entered="2021-04-14", kind="impeller", imp=imp(510, 0.44), text="re-bladed"),
                dict(date="2022-08-15", kind="support", kH=5.0e7, kV=1.6e8, text="regrout")],
        tests=[("2019-11-26", ""), ("2023-05-30", "")]),
    fan("baghouse-fan", 25, 0.60, 0.145, 2.8e7, 3.5, 500, 0.44, imp(430, 0.49), 985, span=1.35, mp=240, kb=1.0e9,
        events=[dict(date="2020-07-13", entered="2020-08-03", kind="impeller", imp=imp(580, 0.45), text="replaced")],
        tests=[("2018-03-05", ""), ("2024-09-17", "brace")]),
    fan("cooler-vent-fan", 26, 0.50, 0.150, 3.2e7, 4.0, 430, 0.45, imp(660, 0.50), 1475, span=1.15, mp=180, kb=8.5e8,
        events=[dict(date="2023-02-27", entered="2023-04-12", kind="shaft", seg=4, d=0.145, text="overhang"),
                dict(date="2019-06-11", kind="support", kH=2.4e7, kV=1.0e8, text="regrout")],
        tests=[("2018-08-21", ""), ("2023-03-14", "")]),
]
BY = {f["name"]: f for f in FANS}
HIDDEN = [f["name"] for f in FANS if f["name"] != EXAMPLE]


def config(f, date=None, impeller=None, cond="", skip=()):
    """The fan as it stood on `date` (all events if None), with `impeller` if given. cond 'brace': the fan-end
    pedestal's horizontal stiffness is 0.35 of its value, its stay removed for the test."""
    sh = copy.deepcopy(f["shaft0"]); im = f["imp0"]; kH, kV = f["kH0"], f["kV0"]; hub = f["hub"]
    for e in sorted(f["events"], key=lambda e: e["date"]):
        if date is not None and e["date"] > date:
            continue
        if e["kind"] == "impeller" and "impeller" not in skip: im = e["imp"]
        if e["kind"] == "shaft" and "shaft" not in skip: sh[e["seg"]][2] = e["d"]
        if e["kind"] == "support": kH, kV = e["kH"], e["kV"]
        if e["kind"] == "hub": hub = e["hub"]
    if impeller is not None: im = impeller
    kHl = [kH, kH * 0.35] if cond == "brace" else kH
    return dict(shaft=[tuple(s) for s in sh], disks=[(0.06,) + tuple(hub), (f["L"],) + tuple(im)],
                bearings=f["bearings"], kb=f["kb"], mp=f["mp"], kpH=kHl, kpV=kV)


def test_freqs(f):
    out = []
    for t in f["tests"]:
        s = Rt.standstill(config(f, t["date"], cond=t["cond"]))
        out.append(dict(t, fH=round(s["H"][0], 2), fV=round(s["V"][0], 2)))
    return out


def truth(f):
    return Rt.criticals(config(f, None, f["new"]), n=2)
