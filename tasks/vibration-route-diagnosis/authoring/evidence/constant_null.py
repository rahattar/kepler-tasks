"""Programs that do not analyse the data, against the bound of 2 wrong out of 60: one that reports every machine as
NONE, and one that reports for every machine the diagnosis the example's analyst gave the example machine of the same
kind (the first one listed).

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import common as C

NONE = '''import csv, os, sys
reg = list(csv.DictReader(open(os.path.join(sys.argv[1], "register.csv"))))
open(sys.argv[2], "w").write("machine,fault,component\\n" + "".join("%s,NONE,none\\n" % r["machine"] for r in reg))
'''
BYKIND = '''import csv, os, sys
pick = {"end-suction pump": ("ELECTRICAL", "motor"), "cooling tower fan": ("GEAR_TOOTH", "gear"),
        "belt-driven fan": ("BELT", "belt"), "screw compressor": ("ROTOR_BAR", "motor"),
        "vertical turbine pump": ("RESONANCE", "structure")}
reg = list(csv.DictReader(open(os.path.join(sys.argv[1], "register.csv"))))
open(sys.argv[2], "w").write("machine,fault,component\\n" + "".join("%s,%s,%s\\n" % ((r["machine"],) + pick[r["kind"]]) for r in reg))
'''

if __name__ == "__main__":
    for label, text in (("every machine NONE", NONE), ("the example's diagnosis for each machine kind", BYKIND)):
        r = C.grade_text(text)
        print("%-50s %d of %d misdiagnosed" % (label, r["wrong"], r["machines"]))
