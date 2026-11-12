"""The shipped systems: five visible examples and eight hidden systems.

Every way the records can be wrong shows in a visible example:
  WH-A  nothing wrong
  WH-B  a gauge with a zero error (B8 reads 0.8 psi high)
  WH-C  a registered C the pipe has aged below (branch lines, register 120, as found 85): decides WH-C's result
  WH-D  a valve off its seat (the sectional valve on cross main A)
  WH-E  two ports entered against each other (A5, A11) and a flow written down wrong (run 3)
In WH-B, WH-D and WH-E the fault shows plainly in the readings (several times the gauges' scatter) but moves
the result by less than the tolerance. The hidden systems carry the same kinds where they decide the result.
"""
from gen import COMMON, GRID_PLAN, NEW, OLD, SUPPLY, TREE_PLAN, WRONG, sz

EXAMPLES = [
    dict(COMMON, tag="WH-A", kind="tree", lines=14, heads=10, feed_ft=180, feed_size="6", crossA_size="6",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=2000, plan=TREE_PLAN,
         groups={"riser": NEW(2006), "feed": OLD(1979, 88), "crossA": NEW(2006), "lines": NEW(2006)},
         supply=SUPPLY(92, 74, 1500)),
    dict(COMMON, tag="WH-B", kind="grid", lines=16, heads=12, feed_ft=150, feed_size="6", crossA_size="4",
         crossB_size="3", branch_size=sz((99, "1-1/2")), density=0.30, area=2500, slope_along=0.02,
         plan=GRID_PLAN,
         groups={"riser": NEW(1984), "feed": NEW(1984), "crossA": OLD(1984, 95), "crossB": NEW(1984),
                 "lines": OLD(1984, 78)},
         sheet=[{"kind": "zero", "port": "B8", "psi": 0.8}], supply=SUPPLY(105, 88, 2000)),
    dict(COMMON, tag="WH-C", kind="tree", lines=12, heads=9, feed_ft=240, feed_size="6", crossA_size="4",
         branch_size=sz((5, "2"), (99, "1-1/2")), density=0.15, area=1500, plan=TREE_PLAN,
         groups={"riser": NEW(1991), "feed": OLD(1991, 92), "crossA": NEW(1991), "lines": WRONG(1991, 120, 85)},
         supply=SUPPLY(95, 80, 1200)),
    dict(COMMON, tag="WH-D", kind="grid", lines=14, heads=10, feed_ft=160, feed_size="6", crossA_size="4",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.25, area=2000, plan=GRID_PLAN,
         groups={"riser": NEW(1996), "feed": NEW(1996), "crossA": NEW(1996), "crossB": NEW(1996),
                 "lines": OLD(1996, 84)},
         valves={"sectional": 6.0}, supply=SUPPLY(100, 84, 1800)),
    dict(COMMON, tag="WH-E", kind="tree", lines=16, heads=10, feed_ft=200, feed_size="6", crossA_size="4",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=1500, plan=TREE_PLAN,
         groups={"riser": NEW(1988), "feed": NEW(1988), "crossA": OLD(1988, 80), "lines": NEW(1988)},
         sheet=[{"kind": "swap", "ports": ["A5", "A11"]}, {"kind": "flow", "run": 3, "recorded": 0.9}],
         supply=SUPPLY(98, 82, 1400)),
]

HIDDEN_SPECS = [
    dict(COMMON, tag="DC-1", kind="grid", lines=30, heads=24, feed_ft=200, feed_size="8", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.25, area=2500, plan=GRID_PLAN,
         groups={"riser": NEW(2003), "feed": NEW(2003), "crossA": NEW(2003), "crossB": OLD(1981, 70),
                 "lines": NEW(2003)},
         valves={"sectional": 250.0}, supply=SUPPLY(110, 90, 2500),
         shift="a larger grid; the sectional valve far off its seat (factor 250 against 6 in WH-D)"),
    dict(COMMON, tag="DC-2", kind="grid", lines=24, heads=20, feed_ft=160, feed_size="6", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.30, area=2500, plan=GRID_PLAN,
         groups={"riser": NEW(2010), "feed": NEW(2010), "crossA": NEW(2010), "crossB": NEW(2010),
                 "lines": OLD(1988, 84)},
         sheet=[{"kind": "swap", "ports": ["A24", "B24"]}], supply=SUPPLY(100, 84, 2200),
         shift="two ports at one elevation entered against each other, on a grid (WH-E: a tree, ports on one "
               "main), so the static readings do not show it"),
    dict(COMMON, tag="DC-3", kind="tree", lines=18, heads=12, feed_ft=150, feed_size="8", crossA_size="6",
         branch_size=sz((6, "3"), (99, "2-1/2")), density=0.45, area=1800, K=16.8, drain_K=45.0, plan=TREE_PLAN,
         groups={"riser": NEW(2001), "feed": NEW(2001), "crossA": NEW(2001), "lines": OLD(1976, 70)},
         sheet=[{"kind": "flow", "run": 7, "recorded": 0.65}], supply=SUPPLY(115, 95, 2000),
         shift="a flow written down a third low on a drain run, where it bears on the open group "
               "(WH-E: a tenth low on a cross main run); a density and K-factor beyond the examples'"),
    dict(COMMON, tag="DC-4", kind="grid", lines=28, heads=22, feed_ft=220, feed_size="6", crossA_size="6",
         crossB_size="6", branch_size=sz((99, "1-1/2")), density=0.20, area=3000, slope_across=0.01,
         plan=GRID_PLAN,
         groups={"riser": NEW(1990), "feed": WRONG(1990, 120, 78), "crossA": OLD(1990, 96),
                 "crossB": NEW(1990), "lines": OLD(1990, 82)},
         sheet=[{"kind": "zero", "port": "A14", "psi": 4.0}], supply=SUPPLY(108, 92, 3000),
         shift="a registered C wrong on the feed main (WH-C: branch lines of a tree) together with a gauge "
               "4 psi out (WH-B: 0.8 psi); a ceiling sloped across the lines"),
    dict(COMMON, tag="DC-5", kind="tree", lines=12, heads=10, feed_ft=420, feed_size="6", crossA_size="6",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=1500, riser_top_ft=60.0,
         ceiling_ft=64.0, plan=TREE_PLAN,
         groups={"riser": NEW(1998), "feed": OLD(1972, 75), "crossA": NEW(1998), "lines": WRONG(1998, 120, 88)},
         sheet=[{"kind": "swap", "ports": ["L6H10", "L6H5"]}], supply=SUPPLY(78, 52, 1000),
         shift="a registered C wrong on the branch lines and, together with it, the two ports on the drained "
               "line entered against each other; a 60 ft riser and a weak supply"),
    dict(COMMON, tag="DC-6", kind="grid", lines=28, heads=22, feed_ft=180, feed_size="8", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.30, area=2500, plan=GRID_PLAN,
         line_groups={"lines_old": (1, 10)},
         groups={"riser": NEW(2012), "feed": NEW(2012), "crossA": NEW(2012), "crossB": NEW(2012),
                 "lines": NEW(2012), "lines_old": OLD(1979, 72)},
         valves={"feed": 150.0}, sheet=[{"kind": "flow", "run": 5, "recorded": 0.75}],
         supply=SUPPLY(104, 88, 2400),
         shift="the feed main's gate valve off its seat (WH-D: the sectional valve) together with a flow "
               "written down a quarter low; older pipe on the riser-end lines only"),
    dict(COMMON, tag="DC-7", kind="tree", lines=14, heads=11, feed_ft=260, feed_size="6", crossA_size="6",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=1800, plan=TREE_PLAN,
         groups={"riser": NEW(1995), "feed": NEW(1995), "crossA": OLD(1982, 85), "lines": NEW(1995)},
         valves={"sectional": 200.0}, supply=SUPPLY(110, 92, 1600),
         shift="the sectional valve far off its seat on a tree, inside the group the register leaves open"),
    dict(COMMON, tag="DC-8", kind="grid", lines=26, heads=20, feed_ft=170, feed_size="6", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.35, area=2500, slope_across=0.025,
         plan=GRID_PLAN,
         groups={"riser": NEW(2008), "feed": NEW(2008), "crossA": OLD(1985, 90), "crossB": WRONG(2008, 120, 75),
                 "lines": NEW(2008)},
         sheet=[{"kind": "swap", "ports": ["A13", "B13"]}], supply=SUPPLY(112, 96, 2600),
         shift="a registered C wrong on cross main B together with two ports entered against each other "
               "across the grid; a ceiling sloped across the lines"),
]
