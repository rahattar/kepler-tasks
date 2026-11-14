import sys
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/claude/work/core7/authoring/provenance")
import cells
out, n, names = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
for c in cells.CELLS:
    if c["cell"] in names:
        cells.build(c, out, cycles=n)
        print(c["cell"], flush=True)
