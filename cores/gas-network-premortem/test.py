import numpy as np, sys, time
sys.path.insert(0, '.')
import gn
rng = np.random.default_rng(3)
# a medium-pressure town network: a grid of mains 12 x 8 nodes, 300 to 600 m apart, two feeds at opposite corners
nx, ny = 12, 8
nodes = ["N%02d%02d" % (i, j) for i in range(nx) for j in range(ny)]
pipes = []
for i in range(nx):
    for j in range(ny):
        if i + 1 < nx and rng.random() < 0.85:
            pipes.append(("N%02d%02d" % (i, j), "N%02d%02d" % (i + 1, j), rng.uniform(0.3, 0.6), rng.choice([110.0, 160.0, 200.0])))
        if j + 1 < ny and rng.random() < 0.85:
            pipes.append(("N%02d%02d" % (i, j), "N%02d%02d" % (i, j + 1), rng.uniform(0.3, 0.6), rng.choice([110.0, 160.0, 200.0])))
# trunk mains from the feeds
feeds = {"N0000": 5.0, "N1107": 4.85}
net = gn.Net(nodes, pipes, feeds)
n = net.n
# demand: profiled over all nodes, daily cycle, plus 3 large metered customers
hours = np.arange(24 * 14)
base = rng.uniform(40, 160, n); base[[net.ix[f] for f in feeds]] = 0
daily = 1 + 0.45 * np.sin(2 * np.pi * (hours % 24 - 7) / 24) + 0.25 * np.sin(4 * np.pi * (hours % 24 - 5) / 24)
temp_eff = 1 + 0.25 * np.sin(2 * np.pi * hours / (24 * 9))
dem = np.outer(daily * temp_eff, base)
large = {"N0605": 1400.0, "N0903": 900.0, "N0306": 700.0}
for k, v in large.items():
    dem[:, net.ix[k]] += v * (0.8 + 0.2 * (hours % 24 > 6) * (hours % 24 < 20))
print("pipes %d, nodes %d, total demand %.0f to %.0f m3/h" % (len(pipes), n, dem.sum(1).min(), dem.sum(1).max()))
sets = [dict(feeds) for _ in hours]
t0 = time.time(); P, F = net.run(dem, sets, 1.0); print("transient run %.1f s" % (time.time() - t0))
Ps, Fs = net.run(dem, sets, 1.0, steady=True)
tele = ["N0507", "N1000", "N0800", "N0204", "N0907"]
ti = [net.ix[x] for x in tele]
print("min pressure %.3f bar; transient vs steady at telemetry: max |dp| %.1f mbar; feed A share %.2f" % (P.min(), 1000 * np.abs(P[:, ti] - Ps[:, ti]).max(), F[:, 0].sum() / F.sum()))
# condition 1: feed B set point 0.15 bar low
sets2 = [{"N0000": 5.0, "N1107": 4.70} for _ in hours]
P2, F2 = net.run(dem, sets2, 1.0)
print("B drifted -0.15 bar: telemetry shift %s mbar; feed A share %.2f (was %.2f)" % (np.round(1000 * (P2[:, ti] - P[:, ti]).mean(0)), F2[:, 0].sum() / F2.sum(), F[:, 0].sum() / F.sum()))
# condition 2: large customer at N0605 takes 20 per cent more than metered
dem3 = dem.copy(); dem3[:, net.ix["N0605"]] *= 1.0 + 0.2 * 1400 / dem[:, net.ix["N0605"]].mean()
P3, F3 = net.run(dem3, sets, 1.0)
print("meter at N0605 20%% low: telemetry shift %s mbar; feeds total up %.1f%%; unaccounted %.0f m3/h of %.0f" % (np.round(1000 * (P3[:, ti] - P[:, ti]).mean(0)), 100 * (F3.sum() / F.sum() - 1), (F3.sum(1) - F.sum(1)).mean(), F.sum(1).mean()))
# a renewed main (the legible need): one 160 mm pipe replaced by 200 mm
