# FP-12: Water supply rating of sprinkler risers

## 1. Scope

FP-12 is the method by which this site rates the water supply of a sprinkler riser that no longer gets its placard
pressure. It fixes the condition the rating refers to, the pressure budget from the city main to the base of the
riser, the way the riser's limit is named, and what the rating reports. It applies to a wet-pipe riser fed from the
yard main through its own lead-in, the yard main taking its water from the city main through the site's one
connection.

## 2. The reference condition

Every riser is rated at the same condition, whatever its records were taken at:

- the riser taking its **placard flow** (register);
- **500 gpm** of hose taken from the yard main's hydrants at the same time, which passes through the
  connection and through no lead-in;
- nothing else flowing on the site;
- the city main at its **reference static**: the mean of the utility's pressure record at the connection, referred
  to the site datum, over the readings timed from 17:00 up to but not including 20:00 on the working days (Monday
  to Friday) of the reference quarter, which the audit note names;
- the site as it stands on the audit date.

## 3. The pressure budget

Pressures are in psi at the site datum and flows in gpm. With q the flow through the riser's lead-in and Q the flow
through the connection, the pressure at the base of the riser is

    p_base(q, Q) = S - d_main(Q) - d_bfp(Q) - d_lead(q) - d_valve(q) - d_check(q)

where S is the city main's static pressure at the connection. The base of the riser is the supply side of its alarm
valve, at the site datum. The riser's supply gauge and its main drain are on the supply side of the alarm valve.

### 3.1 City main

    d_main = B * (Q / 1000)^1.85

B is the fall in the main's pressure at the connection when 1000 gpm is drawn from it. It is identified from the
utility's flow tests of the main.

### 3.2 Backflow preventer

    d_bfp = h_b + (Q / Cv_b)^2        for any flow towards the site

h_b is the assembly's opening differential, which does not depend on the flow, and Cv_b its flow coefficient. Both
are the assembly's own, as it stands, and are identified from the site's records. The maker's figures in the site
data describe an assembly as new.

### 3.3 Lead-in

    d_lead = 4.52 * L * q^1.85 / (C^1.85 * d^4.87)

L is the lead-in's equivalent length in ft (register), which takes in its fittings and the riser's pipework up to
the supply gauge, and d its internal diameter in inches (site data). Cement-lined ductile iron keeps C 140 through
its life. Unlined cast iron is C 100 when laid and loses C as it ages, at a rate that differs from one lead-in to
the next; its C is identified from the riser's own records.

### 3.4 Control valve

    d_valve = (q / Cv)^2

A control valve fully open has the Cv of the site data. A control valve that is not fully open has a smaller one,
identified from the riser's own records.

### 3.5 Lead-in check valve

    d_check = h_c + (q / Cv_c)^2

for a riser whose lead-in has one (register). h_c is the valve's opening differential, identified from the riser's
own records; Cv_c is the figure of the site data.

## 4. The limit

A riser is limited by the element of the budget with the largest loss at the reference condition. It is named

- `city-main` for d_main,
- `backflow` for d_bfp,
- `lead-in` for d_lead,
- `valve` for d_valve,
- `check` for d_check.

## 5. What the rating reports

For each riser:

- its **limit**;
- **p_base**, the pressure at the base of the riser at the reference condition, in psi;
- **q_avail**, the largest flow the riser can take with its placard pressure (register) still at its base, in gpm:
  the flow q at which p_base(q, q + 500) equals the placard pressure, everything else as at the reference
  condition.
