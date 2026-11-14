"""Writes the wrong programs into wrong/, each the reference with one change.
  be_one     backward Euler hardening laws (the usual return mapping), one step a ramp
  be_sub8    backward Euler with 8 equal substeps a ramp
  exact_seq  the exact laws, but each line carried on its own, one after another"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "ref_ratchet.py")).read()
os.makedirs(os.path.join(HERE, "wrong"), exist_ok=True)

EXP_ITER = '''                ex = np.exp(-G * dp[..., None]); a = X - nn[..., None] * sat
                Xn = (nn[..., None] * sat + a * ex).sum(-1); dX = (G * a * ex).sum(-1)
                eb = (R - Q) * np.exp(-b * dp)
                sig = tr - E * nn * dp
                g = np.where(act, nn * (sig - Xn) - Q - k0 - eb, 0.0)
                dgdp = np.where(act, nn * dX - E + b * eb, 1.0)
'''
BE_ITER = '''                den = 1 + G * dp[..., None]; num = X + nn[..., None] * C * dp[..., None]
                Xn = (num / den).sum(-1); dX = -((nn[..., None] * C * den - num * G) / den ** 2).sum(-1)
                bd = 1 + b * dp; kn = k0 + (R + b * Q * dp) / bd; dkn = (b * Q * bd - (R + b * Q * dp) * b) / bd ** 2
                sig = tr - E * nn * dp
                g = np.where(act, nn * (sig - Xn) - kn, 0.0)
                dgdp = np.where(act, nn * dX - E - dkn, 1.0)
'''
EXP_COMMIT = '''            ex = np.exp(-G * dp[..., None])
            X = nn[..., None] * sat + (X - nn[..., None] * sat) * ex
            R = Q + (R - Q) * np.exp(-b * dp)
'''
BE_COMMIT = '''            X = (X + nn[..., None] * C * dp[..., None]) / (1 + G * dp[..., None])
            R = (R + b * Q * dp) / (1 + b * dp)
'''
PARTS = "        parts = 2 if np.any(P[:, k] != P[:, k - 1]) else 1\n"
for a in (EXP_ITER, EXP_COMMIT, PARTS):
    assert src.count(a) == 1, a[:60]
be = src.replace(EXP_ITER, BE_ITER).replace(EXP_COMMIT, BE_COMMIT)
open(os.path.join(HERE, "wrong", "be_one.py"), "w").write(be)
open(os.path.join(HERE, "wrong", "be_sub8.py"), "w").write(be.replace(PARTS, "        parts = 8\n"))
# exact_seq: run main once per line by restricting the lines read
seq = src.replace('''    lines = list(csv.DictReader(open(os.path.join(wd, "lines.csv"))))''',
                  '''    lines = [l for l in csv.DictReader(open(os.path.join(wd, "lines.csv"))) if ONLY is None or l["line"] == ONLY]''')
seq = seq.replace('''    with open(out, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["row", "ratchet_pct"]); w.writerows(rows)''', '''    return rows''')
seq = seq.replace('''if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])''', '''if __name__ == "__main__":
    allrows = []
    for l in csv.DictReader(open(os.path.join(sys.argv[1], "lines.csv"))):
        ONLY = l["line"]
        allrows += main(sys.argv[1], sys.argv[2])
    with open(sys.argv[2], "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["row", "ratchet_pct"]); w.writerows(allrows)''')
seq = seq.replace("ITS = [0]\n", "ITS = [0]\nONLY = None\n")
open(os.path.join(HERE, "wrong", "exact_seq.py"), "w").write(seq)
print("written", sorted(os.listdir(os.path.join(HERE, "wrong"))))
