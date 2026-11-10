# ---- reference controller ----
#
# Online sag estimation plus predictive constraint riding.
#
#   * A bank of sag hypotheses is propagated through the identified model with the
#     commands actually issued. Each period the two pyrometer spots update the likelihood
#     of every hypothesis; the hypotheses still plausible form the live set.
#   * The command is the largest pressure that, held for the lookahead horizon, keeps the
#     predicted zone difference under the limit minus a guard for EVERY live extreme. The
#     actuator lag is inside the model, so the lookahead sees the pressure that will
#     actually arrive.
#   * The wafer is released when every live hypothesis predicts a mass mean under the
#     target minus a margin.
#
# The live set starts as the whole stated sag range, so the first commands are safe for
# the worst wafer; within a few tenths of a second the spots separate the hypotheses and
# the controller rides the limit for the wafer actually on the plate.


class Controller:
    N_RINGS = 30
    SAG_GRID_M = np.linspace(-55e-6, 55e-6, 23)
    SIGMA_EFF_K = 0.6          # spot noise plus the model's own error
    LIVE_RATIO = 1e-3          # posterior relative to the best, still considered possible
    GUARD_K = 0.6
    RELEASE_MARGIN_C = 0.35
    HORIZON_S = 1.2
    N_CAND = 32
    SUB_DT = 0.01

    def __init__(self, station, wafer):
        p = PARAMS
        self.grid = Grid(self.N_RINGS, p["r_wafer_m"], p["r_split_m"],
                         p["spot_center_m"], p["spot_edge_m"])
        self.m = Model(self.grid, p["wafer"], p["C_plate"], p["G_chiller"], p["tau"])
        sid, film = station["station"], wafer["film"]
        self.J = p["J"][sid][film]
        h = len(self.SAG_GRID_M)
        d_in = station["inner_standoff_um"] * 1e-6
        d_out = station["outer_standoff_um"] * 1e-6
        self.gap = self.m.gap(np.full(h, d_in), np.full(h, d_out), self.SAG_GRID_M)
        self.Jv = np.full((h, 1), self.J)
        self.Tset = station["plate_setpoint_C"] + 273.15
        self.Tsv = np.full((h, 1), self.Tset)
        self.loglik = np.zeros(h)
        self.state = None
        self.last_cmd = p["p_idle"]
        self.p_min, self.p_max = p["p_min"], p["p_max"]
        self.t_target, self.zone_cap = p["t_target"], p["zone_cap"]
        self.cands = np.exp(np.linspace(math.log(self.p_min), math.log(self.p_max),
                                        self.N_CAND))[:, None]
        self.n_sub = int(round(p["ctrl_dt"] / self.SUB_DT))
        self.n_look = int(round(self.HORIZON_S / self.SUB_DT))

    def _propagate(self):
        Tw, Tp, P = self.state
        Pc = np.full((len(Tw), 1), self.last_cmd)
        for _ in range(self.n_sub):
            Tw, Tp, P = self.m.step(Tw, Tp, P, Pc, self.gap, self.Jv, self.Tsv, self.SUB_DT)
        self.state = (Tw, Tp, P)

    def _best_command(self, rows):
        Tw, Tp, P = self.state
        k = len(self.cands)
        n = len(rows)
        W = np.repeat(Tw[rows], k, axis=0)
        Q = np.repeat(Tp[rows], k, axis=0)
        PP = np.repeat(P[rows], k, axis=0)
        Pc = np.tile(self.cands, (n, 1))
        gap = np.repeat(self.gap[rows], k, axis=0)
        J = np.full((n * k, 1), self.J)
        Ts = np.full((n * k, 1), self.Tset)
        ok = np.ones(n * k, bool)
        lim = self.zone_cap - self.GUARD_K
        for _ in range(self.n_look):
            W, Q, PP = self.m.step(W, Q, PP, Pc, gap, J, Ts, self.SUB_DT)
            ok &= self.m.zone_dT(W) <= lim
        ok = ok.reshape(n, k).all(axis=0)          # safe for every planning hypothesis
        if not ok.any():
            return self.p_min
        return float(self.cands[np.flatnonzero(ok)[-1], 0])

    def step(self, t, reading):
        if self.state is None:
            T0 = 0.5 * (reading["center_C"] + reading["edge_C"]) + 273.15
            h = len(self.SAG_GRID_M)
            self.state = (np.full((h, self.grid.n), T0), np.full((h, 1), self.Tset),
                          np.full((h, 1), PARAMS["p_idle"]))
        else:
            self._propagate()
        Tw = self.state[0]
        c, e = self.m.spots(Tw)
        self.loglik += -0.5 * ((c - reading["center_C"]) ** 2
                               + (e - reading["edge_C"]) ** 2) / self.SIGMA_EFF_K ** 2
        rel = np.exp(self.loglik - self.loglik.max())
        live = np.flatnonzero(rel >= self.LIVE_RATIO)
        if float(self.m.t_mean(Tw[live]).max()) <= self.t_target - self.RELEASE_MARGIN_C:
            return {"release": True}
        rows = np.unique([live[0], live[-1]])
        self.last_cmd = self._best_command(rows)
        return {"pressure_torr": self.last_cmd, "release": False}
# ---- end reference controller ----
