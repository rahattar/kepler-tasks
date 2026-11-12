import os, random, sys
import gen
case = list(gen.HIDDEN[-1]); case[7] = 600
name, brg, pts = gen.make(tuple(case), random.Random(4128))
gen.write("core/hidden", name, brg, pts)
print(name, len(pts), flush=True)
