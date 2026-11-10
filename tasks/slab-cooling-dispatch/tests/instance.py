"""Episodes for the two-zone TABS group: schedules (with holidays), tariff, occupancy, gains, forecasts."""
import numpy as np
from weather import dow, SPD
from zone import WEST, EAST, gain_inputs, blinds_series
from wx import span_weather, SPAN_D0, HID_D0, HID_D1

DT = 900.0
LOG_D0, LOG_D1 = 139, 195
WARM_D0 = SPAN_D0
LO_OCC, HI_OCC = 21.0, 26.0
ISSUE = 24
FC_LEN = 216
HOLIDAYS = (148, 184, 246)          # 2017-05-29 Memorial Day, 07-04, 09-04 Labor Day
ZONES = ("west", "east")
ZP = dict(west=WEST, east=EAST)
KAPPA = 0.25                        # forecast damps the diurnal temperature swing by this fraction


def schedules(d0, d1):
    n = (d1 - d0) * SPD
    day = d0 + np.arange(n) // SPD
    t_h = (np.arange(n) % SPD) * 24.0 / SPD
    wk = (dow(day) < 5) & ~np.isin(day, HOLIDAYS)
    occ = wk & (t_h >= 8) & (t_h < 18)
    doas = np.where(wk & (t_h >= 6) & (t_h < 19), 1.0, WEST["doas_night"])
    price = np.where(wk & (t_h >= 12) & (t_h < 19), 0.18, 0.06)
    return dict(occ=occ, doas=doas, price=price, t_h=t_h, dow=dow(day), day=day, workday=wk)


def internal_gain(sch, scale, p):
    lunch = np.where((sch["t_h"] >= 12) & (sch["t_h"] < 13), 0.8, 1.0)
    return np.where(sch["occ"], p["gain_occ"] * scale * lunch, p["gain_base"])


def gains(sch, Iv, scale, p, down0=None):
    I_prev = np.concatenate([[0.0], Iv[:-1]])
    b, down_end, states = blinds_series(sch["occ"], sch["t_h"], I_prev, down0, p, keep=True)
    q = internal_gain(sch, scale, p)
    Qa, Qm, Qs, Qg = gain_inputs(q, Iv, b, p)
    return dict(Qa=Qa, Qm=Qm, Qs=Qs, Qg=Qg, qint=q, blinds=b, down_end=down_end, down=states)


def occupancy(d0, d1, seed):
    """Per-zone scale: day-to-day (sd 12%, correlated 0.6 between zones) x within-day (sd 8%)."""
    rng = np.random.default_rng(seed)
    nd = d1 - d0
    z1 = rng.standard_normal(nd); z2 = rng.standard_normal(nd)
    out = {}
    for name, z in (("west", z1), ("east", 0.6 * z1 + 0.8 * z2)):
        day = np.clip(np.exp(0.12 * z - 0.0072), 0.7, 1.3)
        nb = nd * 48
        zz = np.zeros(nb)
        for i in range(nb):
            zz[i] = (0.6 * zz[i - 1] if i % 48 else 0.0) + 0.8 * rng.standard_normal()
        out[name] = np.repeat(day, SPD) * np.repeat(np.exp(0.08 * zz - 0.0032), 2)
    return out


def episode(d0, d1, occ_seed, wx_seed, down0=None):
    W = span_weather(wx_seed)
    s = slice((d0 - SPAN_D0) * SPD, (d1 - SPAN_D0) * SPD)
    wx = dict(Tout=W["Tout"][s].copy(), Iw=W["Iw"][s].copy(), Ie=W["Ie"][s].copy())
    sch = schedules(d0, d1)
    occ = occupancy(d0, d1, occ_seed)
    g = {}
    for z, I in (("west", wx["Iw"]), ("east", wx["Ie"])):
        g[z] = gains(sch, I, occ[z], ZP[z], None if down0 is None else down0[z])
    lo = np.where(sch["occ"], LO_OCC, 10.0)
    hi = np.where(sch["occ"], HI_OCC, 35.0)
    return dict(d0=d0, d1=d1, n=(d1 - d0) * SPD, wx=wx, sch=sch, g=g, lo=lo, hi=hi, wx_seed=wx_seed)


def running_mean(x, w=SPD):
    pad = np.concatenate([np.full(w // 2, x[0]), x, np.full(w // 2, x[-1])])
    c = np.convolve(pad, np.ones(w) / w, mode="same")
    return c[w // 2:w // 2 + len(x)]


class Forecasts:
    """Issued every 6 h for 54 h. Outdoor temperature: the diurnal swing about the 24-h mean is damped
    by KAPPA (a systematic bias, as in coarse NWP), plus an error growing from 0.6 K at issue to 2.5 K
    at 48 h, smooth in time so successive issues agree. Facade irradiances: per-day multiplicative
    error, shrinking at short lead, common to both facades (cloudiness)."""

    def __init__(self, ep, seed, sig0=0.6, sig48=2.5, cloud_err=0.25):
        rng = np.random.default_rng(seed)
        W = span_weather(ep["wx_seed"])
        self.g0 = (ep["d0"] - SPAN_D0) * SPD
        self.T, self.Iw, self.Ie = W["Tout"], W["Iw"], W["Ie"]
        self.Tm = running_mean(self.T)
        n = len(self.T)
        a = 0.985
        z = np.zeros(n); z[0] = rng.standard_normal()
        for i in range(1, n):
            z[i] = a * z[i - 1] + np.sqrt(1 - a * a) * rng.standard_normal()
        self.z = z
        self.ce = cloud_err * rng.standard_normal(n // SPD + 3)
        self.sig0, self.sig48 = sig0, sig48
        self._cache = {}

    def issue(self, s):
        if s in self._cache:
            return self._cache[s]
        idx = self.g0 + np.arange(s, s + FC_LEN)
        idx = np.minimum(idx, len(self.T) - 1)
        lead_h = np.arange(FC_LEN) * 0.25
        sig = self.sig0 + (self.sig48 - self.sig0) * lead_h / 48.0
        T = self.Tm[idx] + (1 - KAPPA) * (self.T[idx] - self.Tm[idx]) + sig * self.z[idx]
        ce = self.ce[idx // SPD] * np.clip(lead_h / 24.0, 0.15, 1.0)
        out = dict(issued_step=s, Tout=T, Iw=np.clip(self.Iw[idx] * (1 - ce), 0, None),
                   Ie=np.clip(self.Ie[idx] * (1 - ce), 0, None))
        self._cache[s] = out
        return out

    def latest(self, t):
        return self.issue((t // ISSUE) * ISSUE)


def debias_T(fT, kappa=KAPPA):
    """What a user of the archive can do: undo the damping about the forecast's own 24-h mean."""
    m = running_mean(fT)
    return m + (fT - m) / (1 - kappa)
