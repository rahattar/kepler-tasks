"""Programs written to the example sites, through the checker: the examples, then the six sites.

    python3 register_run.py > register_run.txt
"""
import json
import os
import shutil

import common
import variants

KINDS = (("register", "one sample for each listed system that was renewed"),
         ("register_spare", "the same, the rest of the allowance on unsampled tanks, a tank that disagrees keeps its own figures"),
         ("on_file_only", "charges sorted by analysis for the oil on file, the order still one sample for each listed system"))


def main():
    print("Programs made from the reference by variants.py, run by tests/grade_program.py")
    for kind, what in KINDS:
        program = variants.build(kind)
        print()
        print("%s: %s" % (kind, what))
        root, sites, truths, books = common.visible_as_sites()
        seen = common.assess(program, sites=sites, truths=truths, books=books)
        print("  the two example sites: %s" % ("accepted" if seen.accepted else "NOT ACCEPTED"))
        for name, entry in seen.sites.items():
            print("    " + common.line(name, entry))
        shutil.rmtree(root)
        outcome = common.assess(program)
        failed = [name for name, entry in outcome.sites.items() if entry.get("points_out_of_band", 1)]
        print("  the six sites: %s, %d of %d sites with loads out of band" % (
            "accepted" if outcome.accepted else "not accepted", len(failed), len(outcome.sites)))
        for name, entry in outcome.sites.items():
            print("    " + common.line(name, entry))
            if entry.get("points_out_of_band"):
                with open(os.path.join(common.SITES, name, "site.json")) as handle:
                    allowance = json.load(handle)["lab_samples"]
                print("      allowance %d, samples ordered %d; worst %s" % (
                    allowance, len(entry["laboratory_order"] or []), entry["worst"]))
        os.unlink(program)


if __name__ == "__main__":
    main()
