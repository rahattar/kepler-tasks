import numpy as np, time
from tank import Tank
QD = 600 / 3600.0
rng = np.random.default_rng(5)
def schedule(days, start_dow=0, design_nights=(), design_days=(), seed=0):
    r = np.random.default_rng(seed)
    hours = []
    for d in range(days):
        dow = (start_dow + d) % 7
        fc = 1.0 if d in design_nights else r.uniform(0.3, 0.7)
        fd = 1.0 if d in design_days else r.uniform(0.3, 0.8)
        for h in range(24):
            Tamb = 18 + 8 * np.sin(2 * np.pi * (h - 9) / 24)
            hr = dict(T_in_charge=5.0 + 0.3 * r.normal(), T_in_dis=12.5 + 0.5 * r.normal(), T_amb=Tamb)
            if dow >= 5:
                hr.update(Q=0.0, mode="standby")
            elif h >= 22 or h < 6:
                hr.update(Q=fc * QD, mode="charge")
            elif 10 <= h < 18:
                hr.update(Q=-fd * QD, mode="discharge")
            else:
                hr.update(Q=0.0, mode="standby")
            hours.append(hr)
    return hours
SZ = np.arange(0.5, 14.0, 1.0)
hist = schedule(28, start_dow=0, seed=1)
fc = schedule(7, start_dow=0, design_nights=(0, 1, 2, 3, 4), design_days=(1, 2, 3), seed=2)
def full(tank_kw, dz=0.02):
    t = Tank(dz=dz, **tank_kw)
    T0 = np.full(t.n, 12.5)
    T1, e1, p1 = t.run(T0, hist, SZ)
    T2, e2, _ = t.run(T1, fc)
    days = [e2[i * 24:(i + 1) * 24].sum() for i in range(7)]
    return T1, np.array(days), p1
t0 = time.time()
_, sound, ps = full({})
print("run %.1f s" % (time.time() - t0))
_, blocked, pb = full({"L_diff": 60.0})
_, leaky, pl = full({"leak": 1.5 / 3600})
print("forecast usable MWh per day, sound  ", np.round(sound, 2))
print("                          blocked   ", np.round(blocked, 2), " diff %", np.round(100 * (blocked / sound - 1), 1))
print("                          leak 1.5  ", np.round(leaky, 2), " diff %", np.round(100 * (leaky / sound - 1), 1))
print("history sensor diff blocked vs sound: rms %.2f K max %.2f K" % (np.sqrt(((pb - ps) ** 2).mean()), np.abs(pb - ps).max()))
print("history sensor diff leak vs sound:    rms %.2f K max %.2f K" % (np.sqrt(((pl - ps) ** 2).mean()), np.abs(pl - ps).max()))
np.save("ps.npy", ps); np.save("pb.npy", pb); np.save("pl.npy", pl)
