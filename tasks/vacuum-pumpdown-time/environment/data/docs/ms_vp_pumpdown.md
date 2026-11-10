# MS-VP Pump-down time of vacuum chambers (owner's standard, revision 3)

1. The pump-down time of a job is the time from the start of roughing, with the chamber at 1013 mbar after the job's
   air vent, to the first time the chamber pressure reaches the job's process pressure. It is computed for the
   chamber as it is on the job's date.
2. The chamber pressure p (mbar) follows V dp/dt = -S_eff p + Q(t), where:
   - V (L) is the volume pumped: the chamber and everything open to it on the chamber side of the gate valve;
   - roughing runs until p reaches the crossover pressure of the chamber's controller; from then the turbo pump pumps
     the chamber through the high-vacuum port and the roughing pump no longer does;
   - S_eff = S C / (S + C): in roughing, S is the roughing pump's speed at p and C the roughing line's conductance;
     in high vacuum, S is the turbo pump's speed at p and C the conductance of the high-vacuum port;
   - pump speeds come from the pump curves of `vacuum_data.md`, linear in log10 p between the points and held beyond
     them;
   - the roughing line's conductance is Knudsen's for air at 20 C, C = 135 D^4 p / L + 12.1 D^3 / L
     (1 + 192 D p) / (1 + 237 D p) L/s, with D the bore and L the length in cm and p the chamber pressure in mbar.
3. The gas load is Q(t) = Q_L + Q_w(t) + sum A q1 (t / 1 h)^-alpha (mbar L/s), with t in hours from the start of
   roughing, held at its 3-minute value before 3 minutes:
   - Q_L is the chamber's air leak, constant;
   - Q_w(t) = Q_w1 (t / 1 h)^-alpha_w is the gas load of the chamber's walls and internals after an air vent;
   - the sum runs over the surfaces in the chamber that its walls' gas load does not include: a load, and any spool
     piece, with q1 and alpha of their material from the outgassing table of `vacuum_data.md` and A their area (cm2).
4. Q_L, Q_w1 and alpha_w are fitted to the chamber's pump-down records after an air vent. In high vacuum, the gas
   load during a record is S_eff p + V dp/dt.
5. Pressures: a gauge's indicated pressure times its calibration factor (its certificate) is the pressure for air.
   Below the crossover the residual gas is water vapor, and a cold cathode gauge's pressure for water vapor is 1.12
   times its pressure for air.
