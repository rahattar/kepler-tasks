# Growth model used by process engineering (both hot zones)

The crucible lift holds the melt level fixed, so the meniscus height h (interface above the free melt surface)
changes at the pull rate minus the growth rate:

    dh/dt = v_pull - v_growth

The growth rate is the zero-superheat value v0(L) (design sheet), shifted by crucible rotation and run offsets,
plus a meniscus term, minus the superheat term:

    v_growth = v0(L) + rotation and run terms + 0.30 (h - 6.8) - 0.050 S

Here h is in mm, the meniscus coefficient 0.30 is in 1/min, the equilibrium meniscus height is 6.8 mm, and S is the
melt superheat at the interface in K.

The diameter follows the growth angle. A meniscus above equilibrium narrows the crystal:

    dD/dt = -2 v_growth * 0.24 (h - 6.8)        (0.24 rad per mm of meniscus height)

The bright-ring camera reads D + offset - 1.2 (h - 6.8) plus about 0.15 mm noise.

Perfect-silicon quality is set by V/G at the interface, where V is the growth rate (not the pull rate) and G is the
axial gradient. The perfect-silicon recipe gives V/G as a growth-rate program along the body, computed from the
HZ-B thermal model's G(L). The defect-free window is +-1 % of the program. A growth-rate excursion shows up in
the defect pattern averaged over about 5 mm of crystal.

Melt-surface pyrometer: reads through a purged window whose coating drifts during a run, typically by several K
over a body. Noise is about 0.3 K. Use it for changes over an hour or two, not for absolute superheat.
