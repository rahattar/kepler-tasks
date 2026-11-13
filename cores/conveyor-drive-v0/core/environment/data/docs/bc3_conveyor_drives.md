# BC-3 Belt conveyor lines: drive loads from the feed log

Issue 2. This standard fixes how the drives of a line of belt conveyor flights are calculated through a log of
the feed onto the line. It states the physical model and what each result means. How it is computed is left
to the analyst.

## 1 Scope and conventions

A line is a row of flights in series: the first is fed from the log, and each flight discharges over its head
onto the tail of the next. A flight is one endless belt on idlers with one to three drives and a gravity
take-up. SI units; g = 9.80665 m/s2. Feed is in t/h, power in kW. Distance x along a flight runs from its
loading point at the tail to its head, a length L.

## 2 The load on the belt

The load lies on the belt where it was put and rides with it. The belt speed v of a flight is the speed its
unstretched belt passes a fixed point; it changes as the drives' loads change. Feed q arriving at the tail of a
flight goes onto the belt at once, and what reaches the head leaves at once and is the feed of the next flight.

M is the mass of load on the flight, and M_j the mass on section j of its profile. A section has a length l_j
and a rise h_j (negative where the belt runs downhill); L and H are the sums of the lengths and of the rises.

## 3 Resistance

The force the drives of a flight must put on the belt is

    F = C f g [ L (2 m_B + m_c + m_r) + M ] + g sum_j M_j h_j / l_j + q v

with m_B the mass of the belt, m_c and m_r the rotating masses of the carrying and return idlers, each per metre
of flight, f the friction factor of the flight and C its secondary factor. The last term brings the feed up to
belt speed (q in kg/s). The part of F that arises on the return run is R_r = C f g L (m_B + m_r).

## 4 The drives

Every drive is a 1,500 rpm (synchronous) motor with a fluid coupling and a gearbox on a lagged pulley. A drive
whose pulley surface runs at speed u has the slip

    s = 1 - u / v_0,     v_0 = pi D n_0 / (60 i),

where D is the diameter of the pulley over its lagging, i the gear ratio and n_0 = 1,500 rpm. The gearbox input
shaft turns at n_0 (1 - s). The drive takes from the supply

    P = P_r s / s_r

with P_r its rated power and s_r its rated slip, and puts on the belt the force F_d = e P / v_0, e being its
efficiency. P, s and F_d are negative when the belt drives the motor. The forces of a flight's drives add up
to F of section 3.

The belt does not slip bodily on a pulley, but it is elastic: where its tension is T it is stretched by T / K
and runs faster by that fraction, K being the belt stiffness. A drive pulley's surface runs at the speed of the
belt coming onto it: u = v (1 + T_on / K).

## 5 Tensions

The drives of a flight are named by their place. `head1` is the pulley at the head, `head2` a second drive
pulley that the belt reaches straight after `head1`, `tail` the pulley at the tail. The take-up sits straight
after the last head drive and holds the belt tension there at T_t at all times. Going round with the belt:

- leaving the last head drive the tension is T_t;
- along the return run it changes by R_r - m_B g H, so the belt comes onto the tail pulley at T_t + R_r - m_B g H;
- a `tail` drive lowers it by its force; the belt leaves the tail at that tension and it is the tension at the
  loading point;
- each head drive lowers the tension by its force, so the belt comes onto `head2` at T_t plus the force of
  `head2`, and onto `head1` at that plus the force of `head1`.

The traction ratio of a drive is the greater of the tensions on its two sides divided by the lesser.

## 6 What the surveys give

A survey campaign records, with the feed steady for longer than the line takes to carry it through, the feed,
the belt speed of each flight and the input shaft speed and motor power of each drive. Two things the
calculation needs are on no register and are found from the surveys:

- the rated slip s_r of each drive;
- the friction factor f of each flight.

The belt speed of a survey is read from the weigher's speed wheel, which runs on the belt at the loading point:
it is v (1 + T / K) with T the tension there. Hand tachometers read to 0.1 rpm, the speed wheels to 0.05 per
cent and the power meters to 0.5 per cent.

## 7 The log and the results

The log gives the feed onto the first flight at equal steps of time; a feed holds from its step to the next.
The line is empty at the first step. Each flight is calculated at every step, with the load then on it.

For every drive and every interval of the log (a fixed number of steps, in order from the first):

- mean power, kW: the mean of P over the steps of the interval;
- greatest and least power, kW: the greatest and the least P at a step of the interval;
- peak traction: the greatest traction ratio at a step of the interval.
