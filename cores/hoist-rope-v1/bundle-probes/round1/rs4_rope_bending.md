# RS-4 Hoist ropes: bending damage along the rope

Issue 3. This standard fixes how the bending fatigue damage of a crane's hoist rope is reckoned along its
length from the hoist's movement log and the rope's surveys. It states the model and what the result means. How
it is computed is left to the analyst.

## 1 The rope and the reeving

A hoist rope runs from its anchorage on the drum, over the sheaves of the upper and lower blocks, to its dead
end. Its length between the two is L. The hook hangs on n falls of rope. A place on the rope is given by x, the
metres of rope between the drum anchorage and the place.

With the hook at height h, each fall has the length H - h, with H the height of the upper block. A sheave that
has p falls between it and the dead end touches the rope at a distance

    a + p (H - h)

from the dead end, that is at x = L - a - p (H - h), where a is the sheave's offset. The drum is reckoned in
the same way, with p = n, at the point where the rope runs onto it.

## 2 Bendings

A movement takes the hook from one height to another without turning back. In a movement every sheave's point
of touch travels along the rope, and every element of the rope it passes is bent once over that sheave. A
bending over a sheave counts with the sheave's bend weight w: 1 for a sheave, 0.5 for the drum, where the rope
is bent in winding on and straightened in winding off.

## 3 The rope tension

In a movement with a hook load m_h the rope tension is

    S = (m_h + m_b) g / (n e),

with m_b the mass of the lower block, e the reeving efficiency and g = 9.80665 m/s2.

## 4 Endurance

A rope element of diameter d, bent over a sheave of diameter D at a tension S, endures

    lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d)

bendings, S in N and d and D in mm, lg the logarithm to base 10.

| construction | b0     | b1    | b2    | b3     |
|--------------|--------|-------|-------|--------|
| 8x36         | -1.214 | 0.887 | 7.432 | -2.103 |
| 6x36         | -1.371 | 0.934 | 7.518 | -2.146 |

d is the diameter of the element itself, as it was measured at the last survey not later than the movement.

## 5 Damage

An element is a piece of the rope, not a place on the crane. The damage of an element is the sum, over every
bending that piece of rope has had since the rope was put on, of w / N.

The result is given for the rope as it lies at the end of the log: for each station of the rope's last survey,
the damage of the element that lies there. The stations of the result are numbered along the rope from the
drum anchorage.
