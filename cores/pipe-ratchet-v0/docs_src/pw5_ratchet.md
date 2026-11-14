# PW-5 Progressive hoop strain of pressurised pipe walls

Revision B. A pipe wall that carries pressure and also sees through-wall temperature differences in start-ups,
shut-downs and trips can grow a little in diameter with every such event. PW-5 defines how much it has grown,
the ratchet strain, from the line's material and its plant history.

## 1 The wall

The wall is taken in the hoop direction only. It is split through its thickness t into 24 layers of equal
thickness; layer i (i = 0 at the bore, 23 at the outside) has its middle at

    z_i = ((i + 1/2) / 24 - 1/2) t,

measured from the mid-wall towards the outside. All layers share one hoop strain eps.

The temperature varies linearly through the wall, and dT is the bore temperature less the outside temperature.
Only that difference strains the layers against each other, so the thermal strain of layer i is

    eps_th,i = -alpha dT z_i / t.

The stress of layer i is sigma_i = E (eps - eps_th,i - eps_p,i), with eps_p,i its plastic strain. The layers
together carry the pressure p: the mean of the 24 layer stresses is p R / t, with R the mean radius.

## 2 The material

A layer stays elastic while |sigma - X| < k0 + K, and while it flows, |sigma - X| = k0 + K and its plastic
strain changes in the direction of sigma - X. With d eps_p that change and dp = |d eps_p|:

- X = X1 + X2 + X3, the back stress, with dXj = Cj d eps_p - gammaj Xj dp for j = 1, 2, 3;
- K, the growth of the yield stress, with dK = b (Q - K) dp. Q may be negative: the material then softens.

E, alpha, k0, C1 to C3, gamma1 to gamma3, Q and b are the material's, in the line package. A line starts
with every layer at eps_p = 0, X1 = X2 = X3 = 0 and K = 0, at p = 0 and dT = 0.

## 3 The history

A line's history is a list of states, each a pressure and a temperature difference. From one state to the
next both change in proportion, along a straight ramp, slowly enough that nothing depends on rate. The wall's
response is the solution of sections 1 and 2 along every ramp of the history, in order.

## 4 The result

At a state marked as a checkpoint, the ratchet strain is

    eps_r = eps - p R / (t E),

the hoop strain less the elastic membrane strain of that state's pressure, in per cent.
