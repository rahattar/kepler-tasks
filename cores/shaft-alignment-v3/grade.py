import csv, json, sys
import model as M
def grade(path, rig):
    d = json.load(open(rig + "/truth.json"))["trains"]
    got = {r["tag"]: r for r in csv.DictReader(open(path))}
    bad = []
    for tag, t in sorted(d.items()):
        try:
            mv = [float(got[tag][k]) for k in ("v_front_mm", "v_rear_mm", "h_front_mm", "h_rear_mm")]
            ok = M.passes(t, mv)
        except Exception:
            ok, mv = False, None
        if not ok:
            bad.append((tag, [round(x, 3) for x in M.residual(t, mv)] if mv else "missing"))
    return len(d) - len(bad), len(d), bad
if __name__ == "__main__":
    n, m, bad = grade(sys.argv[1], sys.argv[2]); print("%d of %d trains aligned" % (n, m))
    for b in bad: print("  ", b)
