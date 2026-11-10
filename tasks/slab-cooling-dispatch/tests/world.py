"""The fixed world: warm-up and trend-log period under the existing BMS sequence, then the graded period."""
import numpy as np
from instance import episode, Forecasts, WARM_D0, LOG_D0, LOG_D1, HID_D0, HID_D1, SPD, ZONES
from sim import run, make_plants

SEEDS = dict(occ_log=11, occ_hid=12, fc_log=21, fc_hid=22, noise_log=31, noise_hid=32, wx=41)
SWITCH_DAY = 168                 # Jun 17: night-only operation from here on
EAST_STUCK = (155, 160)          # Jun 5-9: east zone valve actuator failed closed


class ExistingSequence:
    def __init__(self, ep):
        self.ep = ep
        self.hist = []

    def __call__(self, obs, t, X=None):
        self.hist.append(obs["outdoor_temp_c"]); self.hist = self.hist[-SPD:]
        m = float(np.mean(self.hist))
        day = self.ep["d0"] + t // SPD
        h = (t % SPD) / 4.0
        if day < SWITCH_DAY:
            sp = float(np.clip(23.0 - 0.6 * (m - 18.0), 16.0, 22.0))
            duty = {"west": 1.0, "east": 1.0}
        else:
            sp = float(np.clip(21.0 - 0.5 * (m - 18.0), 16.0, 22.0))
            on = 1.0 if (h >= 20 or h < 7) else 0.0
            duty = {"west": on, "east": on}
        if EAST_STUCK[0] <= day < EAST_STUCK[1]:
            duty["east"] = 0.0
        return sp, duty


def build(keep_log=True, seeds=None):
    S = dict(SEEDS); S.update(seeds or {})
    plants = make_plants()
    ep_log = episode(WARM_D0, LOG_D1, S["occ_log"], S["wx"])
    fc_log = Forecasts(ep_log, S["fc_log"])
    ctrl = ExistingSequence(ep_log)
    rows = []
    t_log0 = (LOG_D0 - WARM_D0) * SPD

    def logger(t, obs, sp, duty, X, last):
        if keep_log and t >= t_log0:
            rows.append((t, obs, sp, duty, {z: X[z].copy() for z in ZONES}, last))

    X0 = {z: np.full(plants[z].nx, 23.0) for z in ZONES}
    W, X_end = run(ep_log, lambda o, t, X: ctrl(o, t), X0, fc_log, plants=plants, seed=S["noise_log"],
                   logger=logger)
    down0 = {z: ep_log["g"][z]["down_end"] for z in ZONES}
    ep_hid = episode(HID_D0, HID_D1, S["occ_hid"], S["wx"], down0=down0)
    fc_hid = Forecasts(ep_hid, S["fc_hid"])
    return dict(plants=plants, ep_log=ep_log, fc_log=fc_log, log_rows=rows, log_metrics=W, t_log0=t_log0,
                ep_hid=ep_hid, fc_hid=fc_hid, X0_hid=X_end, seeds=S)
