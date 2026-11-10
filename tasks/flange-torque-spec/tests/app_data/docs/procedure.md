# Bolt-up procedure JT-5

The flanged joints listed in joint_schedule.csv are to be assembled with their full bolt patterns. For each joint,
specify the assembly torque to be applied to every bolt, in newton-metres.

## Preload

Tightening a bolt to a torque T develops a preload F in it. For the fasteners used here the handbook relation is
T = K * d * F, with d the bolt nominal diameter and K the nut factor given in fastener_handbook.csv, which also
tabulates the bolt proof loads by size and grade.

## Assembly

The crew tightens each joint in one cross-pattern pass, every bolt brought to the full assembly torque in turn, with
calibrated hydraulic torque wrenches. There is no further pass.

## Trial tightenings

The rig can perform a trial tightening on any joint of the schedule. A single-bolt trial tightens one bolt of the
joint to a torque and reports the torque applied and the preload developed in that bolt: run `trial <joint_id>` to
use the rig's default torque (the handbook torque for the joint's target preload), or `trial <joint_id> <torque_Nm>`
to apply a torque of your choosing. A pattern trial, `trial <joint_id> pattern` (default torque) or
`trial <joint_id> <torque_Nm> pattern`, tightens every bolt of the joint's pattern to the torque in the crew's
sequence and reports the torque applied and the preload then measured in one monitored bolt of the pattern. A
single-bolt trial uses one trial of the allowance and a pattern trial uses two; the allowance is 8 trials in total,
and the rig refuses any trial that would exceed it.

## Records

examples/ holds the records of two earlier assemblies on this flange type, in the same format as the schedule, with
the trial and final measurements taken at the time and the sequence the assembly was tightened in.

## Requirement

Deliver `/app/output/torques.json`: {"torques": {"J01": <N.m>, ...}} with one assembly torque for every joint of
the schedule. A joint is assembled correctly when, after its pattern is tightened, the preload in each of its bolts
is within 6% of the target_preload_per_bolt_kN given for it in joint_schedule.csv and no bolt has been taken past
its proof load. The bolt-up is acceptable when at least 15 of the 16 joints are assembled correctly.
