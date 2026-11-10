"""Weather for the whole simulated span, 15-min steps, from Chicago O'Hare TMY3 (real data).

Logged period (and warm-up): the TMY3 days as they are.
Graded period (and 4 days beyond, for forecast horizons): a seeded generator on the same real data -
each day is a TMY3 day drawn within +/-10 days of its date, shifted by a day-to-day temperature
offset (AR(1), sd 1.0 K), with the midnight discontinuity relaxed over the first 4 hours. Facade
irradiance comes from the drawn day. So the graded weather is real-data-shaped but is not the
public file.
"""
import numpy as np
from weather import year_15min, SPD

SPAN_D0, HID_D0, HID_D1 = 125, 195, 251
SPAN_D1 = HID_D1 + 4
_CACHE = {}


def year_both():
    if "y" not in _CACHE:
        w = year_15min(facade_az=270.0)
        e = year_15min(facade_az=90.0)
        _CACHE["y"] = dict(Tout=w["Tout"], Iw=w["Ivert"], Ie=e["Ivert"])
    return _CACHE["y"]


def span_weather(seed):
    """Arrays over days SPAN_D0..SPAN_D1-1 (index 0 = SPAN_D0 00:00)."""
    key = ("span", seed)
    if key in _CACHE:
        return _CACHE[key]
    y = year_both()
    rng = np.random.default_rng(seed)
    nd = SPAN_D1 - SPAN_D0
    T = np.zeros(nd * SPD); Iw = np.zeros(nd * SPD); Ie = np.zeros(nd * SPD)
    src_days = np.zeros(nd, int)
    delta = 0.0
    for i in range(nd):
        d = SPAN_D0 + i
        if d < HID_D0:
            s = d; off = 0.0
        else:
            s = int(np.clip(d + rng.integers(-10, 11), HID_D0 - 20, 364))
            delta = 0.6 * delta + 0.8 * rng.standard_normal()
            off = delta
        src_days[i] = s
        sl = slice(s * SPD, (s + 1) * SPD)
        Td = y["Tout"][sl] + off
        if i > 0 and d >= HID_D0:
            prev = T[i * SPD - 1]
            jump = prev - Td[0]
            Td = Td + jump * np.clip(1 - np.arange(SPD) / 16.0, 0, 1)
        T[i * SPD:(i + 1) * SPD] = Td
        Iw[i * SPD:(i + 1) * SPD] = y["Iw"][sl]
        Ie[i * SPD:(i + 1) * SPD] = y["Ie"][sl]
    out = dict(Tout=T, Iw=Iw, Ie=Ie, src_days=src_days)
    _CACHE[key] = out
    return out


if __name__ == "__main__":
    for sd in (101, 102):
        w = span_weather(sd)
        h0 = (HID_D0 - SPAN_D0) * SPD
        Th = w["Tout"][h0:h0 + 56 * SPD].reshape(8, -1)
        print(sd, "hidden weekly mean Tout", np.round(Th.mean(1), 1), "max", np.round(Th.max(1), 1),
              "| max step jump %.2f K" % np.abs(np.diff(w["Tout"])).max())
    y = year_both()
    print("TMY hidden-period weekly means", np.round(y["Tout"][HID_D0 * SPD:HID_D1 * SPD].reshape(8, -1).mean(1), 1))
