"""drive.py points OUT | drive.py truth OUT name..."""
import csv, json, os, random, sys, time
import gen

out = sys.argv[2]
if sys.argv[1] == "points":
    rng = random.Random(4127)
    for group, folder in ((gen.VISIBLE, "data/examples"), (gen.HIDDEN, "hidden")):
        for case in group:
            name, brg, pts = gen.make(case, rng)
            gen.write(os.path.join(out, folder), name, brg, pts)
            print(name, len(pts), flush=True)
else:
    for name in sys.argv[3:]:
        folder = "data/examples" if os.path.isdir(os.path.join(out, "data/examples", name)) else "hidden"
        d = os.path.join(out, folder, name)
        brg = json.load(open(os.path.join(d, "bearing.json")))
        pts = [dict(point=r["point"], speed_rpm=float(r["speed_rpm"]), load_N=float(r["load_N"]),
                    load_angle_deg=float(r["load_angle_deg"]), inlet_C=float(r["inlet_C"]))
               for r in csv.DictReader(open(os.path.join(d, "points.csv")))]
        t = time.time()
        res = gen.solve_case(brg, pts)
        rows = list(csv.DictReader(open(os.path.join(d, "points.csv"))))
        gen.write(os.path.join(out, folder), name, brg, rows, res, "expected.csv" if folder != "hidden" else "truth.csv")
        json.dump([{k: (float(v) if not isinstance(v, bool) else v) for k, v in s.items()} for s in res],
                  open(os.path.join(d, "state.json" if folder == "hidden" else "../../../state_%s.json" % name), "w"))
        print(name, "%.0f s" % (time.time() - t), "eps %.3f-%.3f" % (min(s["eps"] for s in res), max(s["eps"] for s in res)), flush=True)
