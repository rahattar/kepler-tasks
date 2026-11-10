# DDC VAV controller: airflow configuration (excerpt)

Reported airflow:

    flow_cfm = K * sqrt(VP - offset)        (0 if VP <= offset)

- `VP` is the velocity-pressure reading in in. w.c. On firmware 3.x the trended `vp_inwc` point is the reading
  after the hourly auto-zero. On firmware 2.4 there is no auto-zero, so `vp_inwc` includes the transducer's zero
  error. A failed auto-zero valve on firmware 3.x is not alarmed: the controller keeps its last zero, so check
  the VP reading with the damper shut.
- `K` (cfm per sqrt(in. w.c.)) and `offset` (in. w.c., default 0) are the two field calibration parameters.
  They are entered per box; the shipped values are the factory K for the inlet size and offset 0.
- The box modulates its damper so that the reported airflow equals the active flow setpoint.

Trended points (15-minute samples): `flow_sp_cfm` (active setpoint), `flow_cfm` (reported airflow with the
present configuration), `vp_inwc`.
