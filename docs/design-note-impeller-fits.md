# Design note: impeller-shrink-fits (latest task, Nov 9 2026)

**Status:** the 20261109c zip fixes two blocking validation failures, obfuscated preflight strings and a stale
verifier_checks.txt; it is awaiting revalidation. Advisory and open: the task.name prefix, and the explanation
fields in task.toml.

**Task:** compressor C-201 rotor. Six spare impellers S1-S6 (FV520B; S5 is Ti-6Al-4V), a balance drum and a
thrust collar (42CrMo4), on a 26NiCrMoV14-5 rotor.
- **Deliverable:** /app/output/bore_sheet.csv, with a bore in mm and an oven temperature per part.
- **Lab:** `cte <material> <T>`, a dilatometer giving the mean expansion from 20 C. The booking is 3 tests, and the
  stated repeatability is 0.3 %.
- **Standard RS-3:**
  - retention (15 MPa and twice the stage torque) at the least interference, at rest and at trip;
  - von Mises stress at the bore at most Re/1.2;
  - clearance of 0.001 d against the seat in the 28.5 C bay, with the oven at or below the heating limit.
- **Windows:** 7-12 um.
- **Seed:** 5437.

## Layers
1. **Four materials, 3 tests.** The rotor steel rises steeply and its seats run up to 190 C. The way out is the
   balance drum certificate's 42CrMo4 mill value.
2. **FV520B once,** at S6's 375 C; extrapolating from 240 C overstates it.
3. **Ti-6Al-4V tested.**
4. **Bay at 28.5 C;** the clearance is checked against the seat in the bay.
5. **Micrometer M-114** reads 4 um low.
6. **Trip** is 110 % (log), not the OEM's 105 %.
7. **S5 is Ti;** the register is stale.
8. **S2 recoated:** the limit is 240 C, not the certificate's 260 C.
9. **S4 spin-tested** at 10500 rpm.
10. **Seat growth at speed** credited.
11. **Allowance** for the stated repeatability.
12. **IT5 for the nominal diameter;** smoothing.

## Calibration (local)
- **xhigh:** 3/3 in rounds 6-9, even as layers were added.
- **Low:** 0/3.
- **Shipped anyway,** because local xhigh runs stronger than official.
