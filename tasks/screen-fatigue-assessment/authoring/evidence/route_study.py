"""Shortcuts against the reference on the shipped house, each with the reference's outage programme (strain survey on
S5, coast-down tests on S6 and S8). Figures: the worst screen's relative miss of the Miner sum.

    python3 route_study.py > route_study.txt
"""
import plans as P


def show(name, plan=P.REF, proxy="median", **kw):
    o = P.opts(**kw)
    w, u, f, _ = P.grade(P.assemble(P.components(o), plan, o, proxy))
    print("  %-92s worst %5.2f (%s)  fails %d  %s" % (name, w, u, len(f), " ".join(f)), flush=True)


print("requirement: within 20 % of each screen's damage\n")
show("reference")
print("\nrecords taken at face value")
show("S4's readings with the loggers' gauge factor 2.00 (its gauges are the 2.12 lot)", gf=False)
show("S2's hot spot extrapolated as if its gauges were at 0.4t and 1.0t (they are at 10 and 30 mm)", pos=False)
show("S7's channels as labelled (swapped at the junction box)", swap=False)
show("S1's G2 as recorded after it got wet (August)", debond="none")
show("S9's G1 as recorded after its drop in July (nothing logged)", s9debond=False)
show("S8's records at the index's 500 samples per second (the spare logger runs at 200)", fs8=False)
show("S9's FAT class without the 32 mm thickness correction", thick=False)
show("S5's rev B gusset at the rev A class (FAT 90)", fat5=False)
show("S6 counted from commissioning instead of its 2025-11-14 replacement", s6=False)
show("S8's starts since 2024-07-01 as logged (the pilot historian counts start and stop commands)", s8starts=False)
show("S9's missing 2024 left out (the production report has it)", s9gap=False)
show("S2's coast-downs after its 2021 bearing job at the commissioning time (the log has 25.0 s)", s2tau=False)
print("\nstops before the brakes (2026-03-02)")
show("coast-downs simulated from a single-mode fit of the braked stops' ring-down", coast="sdof")
show("coast-downs from a single-mode quasi-static resonance curve", coast="quasi")
show("every pre-brake stop counted as a braked stop", coast="braked")
show("pre-brake stops left out", coast="none")
show("starts and stops left out altogether", events=False)
print("\nproxies for what the records do not settle")
show("siblings' largest damage per event (a 'conservative' proxy) instead of their median", proxy="max")
