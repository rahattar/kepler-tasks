# TS-4 Torsional vibration of generating sets through speed changes

Issue 2. This standard fixes how the peak torques of a generating set's shaft line, and the temperature of
its coupling, are worked out for a sequence of speed changes on the test bed.

## 1 Scope

Generating sets with a four-stroke engine, a highly flexible rubber coupling and a generator, run between
600 and 1,800 rpm, in sequences of up to 10 runs and 600 seconds, with ramps of 2 to 60 seconds and holds of
up to 120 seconds.

## 2 The shaft line

The line is four inertias in a chain: the engine (crankshaft and running gear), the flywheel, the coupling's
hub and the generator rotor, J1 to J4 in kg m2, with angles theta1 to theta4. Three elastic connections join
them: the crankshaft (engine to flywheel), the coupling (flywheel to hub) and the generator shaft (hub to
generator). A connection between inertias a and b carries the torque

    T = k (theta_a - theta_b) + c (theta_a' - theta_b')

with its stiffness k in Nm/rad and its damping c in Nms/rad. T12 is the crankshaft torque, T23 the coupling
torque and T34 the generator shaft torque.

## 3 Motion

The engine runs at the speed w(t) of the sequence (section 5), in rad/s; phi(t) is the angle it turns
through, with phi' = w and phi = 0 when the sequence starts. Each inertia's angle is theta_i = phi + q_i.
The engine applies to its own inertia its excitation

    M(t) = sum over orders k of T_k sin(k phi + psi_k)

with each order's amplitude T_k and phase psi_k, and, besides, the torque (J1 + J2 + J3 + J4) w' that carries
the line through the speed change. The engine is also damped by c_e q1', against its own inertia. So

    J1 q1'' = M + (J1 + J2 + J3 + J4) w' - J1 w' - T12 - c_e q1'
    J2 q2'' = - J2 w' + T12 - T23
    J3 q3'' = - J3 w' + T23 - T34
    J4 q4'' = - J4 w' + T34

## 4 The coupling's rubber

The coupling's damping c23 is fixed. Its stiffness falls as its rubber warms:

    k23 = k_ref exp(-a (T - T_ref))

with T the rubber temperature in C, k_ref the stiffness at T_ref and a the softening per kelvin. The rubber
takes the power the coupling dissipates and gives heat to the air around it:

    C_th T' = c23 (q2' - q3')^2 - G (T - T_air)

with its heat capacity C_th in J/K, its cooling G in W/K and the air temperature T_air.

## 5 Runs and the sequence

The runs of a set follow one another in the order of the set's table, each starting at the speed the one
before it ended at. A run with starting speed n_a, final speed n_b (rpm), ramp D and hold H (s) lasts
1 + D + H seconds: it holds n_a for one second, ramps as

    n = n_a + (n_b - n_a) s(x),   s(x) = x - sin(2 pi x) / (2 pi),   x = (t - t_0 - 1) / D

with t_0 the time the run starts, and holds n_b for H seconds. The speed and its rate of change are continuous
through every run.

Before the sequence starts, the set has run at the first run's starting speed long enough to settle, with the
rubber at the set's starting temperature: when the sequence starts the line is in its steady response at that
speed and that temperature.

## 6 Results

For each run, over its time from its start to the end of its hold:

- the peak crankshaft, coupling and generator shaft torques: the largest absolute values T12, T23 and T34
  reach, in kNm;
- the rubber temperature at the end of the run's hold, in C.

## 7 Accuracy

Results are issued to 3 per cent on torques and to 1 K on the rubber temperature.
