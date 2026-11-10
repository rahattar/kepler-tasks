# Design note: vacuum-pumpdown-time (latest task, Nov 9 2026)

**Status:** zip vacuum-pumpdown-time-20261109.zip (md5 e655368cbde01d7c7d4b144b0377471f) is on the Mac. The
instruction is a draft awaiting Alex's approval, including its relevant_experience line.

**Task:** a program `/app/output/pumpdown.py JOB_DIR OUT_JSON` writes `pumpdown_min`, the pump-down time of a vacuum
chamber's job. Right within 4 %; a pass allows at most 1 of 7 hidden chambers wrong.
- **Standard MS-VP:** V dp/dt = -S_eff p + Q(t). Roughing (pump curve, Knudsen line conductance) runs to the
  controller's crossover, then the turbo pumps through the high-vacuum port.
- **Gas load:** Q = Q_L + Q_w1 t^-alpha + table outgassing of loads and spool pieces, held at its 3-minute value.
- **Fit:** Q_L, Q_w1 and alpha from the chamber's air-vent records; the gas load in high vacuum is S_eff p + V dp/dt.
- **Pressures:** cold cathode x calibration factor x 1.12 for water vapor.
- **V** is the volume pumped: the chamber and everything open to it on the chamber side of the gate valve.
- **Chambers:** five outgassing-limited, two (sputter-bay, tool-coater) roughing-limited. Truths 8.2-199 min; the
  example is 66.3 min.

## Layers (each in 2 chambers unless noted)
- **Data-only:**
  - the turbo exchange model appears only in record headers;
  - a gauge serial change appears only in headers;
  - a dated gauge recalibration;
  - a misfiled record of another chamber;
  - the crossover appears only in headers;
  - a load lock merged with no volume given, so the volume comes from the records' roughing.
- **Documented:**
  - record loads;
  - door seal (one leak per seal);
  - internals rebuilt;
  - nitrogen vents;
  - spool piece (volume and area);
  - roughing line rerouted;
  - water vapor factor (5 chambers);
  - job load (5 chambers).
- **Closest single-check miss:** 4.9 % (internals route, 4 wrong). Nominal pump speed misses by 5.9 %, water by 6.6 %.

## Lessons
- Roughing-side layers only matter in roughing-limited jobs. Outgassing-limited times depend on absolute time since
  roughing start, so roughing details wash out.
- A wrong turbo used consistently in the fit and the job cancels (p = Q/S). The trap bites only when records mix
  pumps, so keep most records before the exchange.
- A per-record leak absorbed other faults (internals, pump exchange). One leak per door seal kept them sharp.
- The standard must define V. Before it did, every xhigh probe missed the spool volume.
- Pin probes' temporary files to their own sandbox (DIR/tmp).

## Calibration (local)
- **Round 1** (explicit standard text): low 1/3; xhigh 3/3 failed only on the spool volume.
- **Round 2** (neutral clause 4, merge layer): low 0/3, xhigh 2/3.
- **Round 3** (misfiled record, dated recalibration, V defined): low 0/3 (4-5 wrong); xhigh 1/3 (one missed the
  crossover, one had 3 wrong).

## Evidence
- Reference within 0.14 %; independent within 0.28 %; method spread 0.28 %.
- Nulls 6-7 wrong. Verifier simulation: nop 0, oracle 1. Preflight: 182 checks clean.
