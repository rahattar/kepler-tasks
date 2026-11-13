"""The agent-visible documents, written from the same constants as the sealed definition."""
import ssphys as P
import supply_site as S


def standard():
    return """# FP-12: Water supply rating of sprinkler risers

## 1. Scope

FP-12 is the method by which this site rates the water supply of a sprinkler riser that no longer gets its placard
pressure. It fixes the condition the rating refers to, the pressure budget from the city main to the base of the
riser, the way the riser's limit is named, and what the rating reports. It applies to a wet-pipe riser fed from the
yard main through its own lead-in, the yard main taking its water from the city main through the site's one
connection.

## 2. The reference condition

Every riser is rated at the same condition, whatever its records were taken at:

- the riser taking its **placard flow** (register);
- **%(hose).0f gpm** of hose taken from the yard main's hydrants at the same time, which passes through the
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
the next. Swabbing a lead-in gives some of it back, never to more than C 100. Its C is identified from the riser's
own records.

### 3.4 Control valve

    d_valve = (q / Cv)^2

A control valve fully open has the Cv of the site data, and a valve partly shut a smaller one.

Every control valve stood fully open at the insurer's survey of December 2022 (audit note). A supervised valve
(register) has stayed so: its switch reports it before it has closed far enough to count. A valve that is chained
and locked is moved only for work on its riser, which the maintenance log records, and stands as that work left
it.

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
  the flow q at which p_base(q, q + %(hose).0f) equals the placard pressure, everything else as at the reference
  condition.
""" % dict(hose=S.HOSE_OUTSIDE)


def site_data():
    ids = "\n".join("| %s | %s | %.2f |" % (m, s, d) for (m, s), d in sorted(P.PIPE_ID.items()))
    return """# Site data

## Datum and the utility's transmitter

Pressures on the site are referred to the **site datum**, the finished floor level of the riser rooms, which is
one level across the site. The yard hydrants' outlets are taken as at the datum.

The utility's transmitter PT-0 is on the city main in the connection pit, **%(pit).1f ft below the site datum**. Its
record is the transmitter's own reading. Water stands at %(psift).3f psi per ft.

## Pipe

| material | nominal size, in. | internal diameter, in. |
|---|---|---|
%(ids)s

`DI-CL` is ductile iron, cement lined; `CI` is unlined cast iron. This site's cast iron lead-ins have been found
between C 55 and C 95.

The yard main is a 12 in. cement-lined loop. Its own loss is negligible at the flows of this standard and it is
taken as standing at one pressure.

## Backflow preventer

The connection has one double check assembly, two spring-loaded checks in series between two isolating valves.
The maker's figures for the assembly as new are an opening differential of **%(hb).1f psi** and a flow coefficient
**Cv %(cvb).0f** (gpm at 1 psi). It passes water towards the site only.

## Lead-in check valves

| model | size, in. | opening differential as new, psi | Cv_c |
|---|---|---|---|
| LC-6 | 6 | %(lc6).1f | %(cv6).0f |
| LC-8 | 8 | %(lc8).1f | %(cv8).0f |

A lead-in check is a single spring-loaded check where the lead-in enters the building.

## Control valves

Every riser has an OS&Y gate valve below its supply gauge. Fully open: Cv %(v6).0f in 6 in., Cv %(v8).0f in 8 in.

## Main drains

A main drain discharges to the open air through the riser's drain valve, fully open. Its flow is

    q = K * sqrt(p)

with p the residual pressure on the riser's supply gauge in psi.

| drain valve pattern | K |
|---|---|
| 2 in. angle | %(k2).0f |
| 1-1/2 in. globe | %(k15).0f |

## Hydrant flow by pitot

The flow from one hydrant outlet is

    Q = 29.84 * c * d^2 * sqrt(p_pitot)

with d the outlet's diameter in inches, p_pitot the pitot pressure in the stream in psi and c the outlet's
coefficient. Every outlet on the list below is 2.5 in.

| outlet form | c |
|---|---|
| smooth, rounded | 0.90 |
| square, sharp | 0.80 |
| projecting into the barrel | 0.70 |

| hydrant | on | outlet form |
|---|---|---|
| H-41 | city main, at the connection | smooth, rounded |
| H-42 | city main, 310 ft beyond the connection | smooth, rounded |
| H-43 | city main, 640 ft beyond the connection | square, sharp |
| YH-1 | yard main, building A | smooth, rounded |
| YH-2 | yard main, building C | smooth, rounded |
| YH-3 | yard main, building D | square, sharp |
| WH-6 | SR06's lead-in, at the wall of building C | smooth, rounded |

A wall hydrant stands on a riser's lead-in before the riser's control valve. The register gives how much of the
lead-in's equivalent length lies between the yard main and the hydrant's tee.

## Gauges

Each riser has a digital test gauge on the supply side of its alarm valve, at the height above the datum that the
register gives. The gauges are read to 0.1 psi and repeat to about 0.1 psi. Each has a certificate
(`gauge_certificates.md`).
""" % dict(pit=S.PIT_BELOW_FT, psift=P.PSI_PER_FT, ids=ids, hb=S.BFP_SHEET["h_b"], cvb=S.BFP_SHEET["Cv_b"],
           lc6=S.CHECK_SHEET["LC-6"], lc8=S.CHECK_SHEET["LC-8"], cv6=P.CHECK_CV["6"], cv8=P.CHECK_CV["8"],
           v6=P.VALVE_OPEN_CV["6"], v8=P.VALVE_OPEN_CV["8"], k2=P.DRAIN_K["2 in. angle"],
           k15=P.DRAIN_K["1-1/2 in. globe"])


def records_format():
    return """# The records

All dates and times are local standard time; the site's clocks and the utility's are not put forward in summer.
Pressures are in psi and flows in gpm.

## riser_register.csv

One row for each riser.

- `riser`, `building`
- `lead_in_material`, `lead_in_size_in`: as the pipe table of the site data
- `lead_in_equiv_length_ft`: the equivalent length L of FP-12 clause 3.3
- `laid`: the year the lead-in was laid
- `lead_in_check`: the model of the lead-in's check valve, empty where it has none
- `wall_hydrant`, `wall_hydrant_at_equiv_ft`: the wall hydrant on the lead-in, if it has one, and the equivalent
  length of lead-in from the yard main to the hydrant's tee
- `valve_supervision`: `switch` for a control valve with a supervisory switch, `lock` for one chained and locked
- `main_drain`: the drain valve's pattern
- `supply_gauge_serial`, `supply_gauge_height_ft`: the gauge on the riser and its height above the site datum
- `placard_flow_gpm`, `placard_pressure_psi`: the riser's hydraulic placard, at the base of the riser

## main_drain_log.csv

The monthly round. The tester goes from riser to riser, and at each one opens the main drain fully, reads the
supply gauge once it is steady, and closes the drain. The order of the round changes from month to month.

- `riser`, `date`, `time`: the riser and when its gauge was read
- `gauge_serial`: the serial of the gauge read
- `residual_psi`: the supply gauge with the drain fully open

## utility_pressure.csv

The utility's record of transmitter PT-0, one reading every 30 minutes. No reading of the record was taken while
the site was drawing water for a test.

- `timestamp`, `pressure_psi`

## utility_flow_tests.csv

The utility's flow tests of the city main. The pressures are read at the residual hydrant, first with no hydrant
flowing and then with the flow hydrant's outlets discharging.

- `date`, `time`
- `residual_hydrant`, `flow_hydrant`
- `outlets_flowing`: the number of outlets of the flow hydrant that were open
- `static_psi`, `residual_psi`: at the residual hydrant
- `pitot_psi`: the pitot pressure in the stream of each open outlet

## yard_flow_tests.csv

The site's flow tests of its own hydrants, each spring and autumn: a hydrant is flowed, and the pressure is read
on the supply gauge of a riser that is not flowing. For a wall hydrant the gauge read is that of the riser whose
lead-in the hydrant stands on.

- `date`, `time`
- `flow_hydrant`, `outlets_flowing`, `pitot_psi`: as above
- `gauge_riser`: the riser whose supply gauge was read
- `residual_psi`: that gauge with the hydrant flowing

## maintenance_log.csv

- `date`, `item` (a riser, or `connection`), `work`

## gauge_certificates.md

One certificate for each gauge serial.
"""


def audit_note():
    return """# Audit note, October 2026

The insurer's survey of September 2026 found that none of the ten risers SR01 to SR10 is supplied at its placard
pressure. Each is to be rated under FP-12.

- **Audit date:** %(audit)s.
- **Reference quarter:** %(q0)s to %(q1)s.
- **Risers:** SR01 to SR10, as the register.
- **Valves:** the insurer's survey of December 2022, the last before the records begin, found every control valve
  fully open.

The records run from %(l0)s to %(l1)s: the monthly round's log, the utility's record of the main's pressure at
the connection, the utility's flow tests of the main, the site's flow tests of its own hydrants, the
maintenance log and the gauge certificates.

The folder `example` holds the records of SR00, a riser of building E, for 2022, the year before that building
was taken down. They are in the same formats and units.
""" % dict(audit=S.AUDIT_DATE.strftime("%Y-%m-%d"), q0=S.REF_FROM.strftime("%Y-%m-%d"),
           q1=S.REF_TO.strftime("%Y-%m-%d"), l0=S.LOG_START.strftime("%Y-%m-%d"), l1=S.LOG_END.strftime("%Y-%m-%d"))


def order():
    return """# The flow test order

The audit can call on **one flow test**, ordered once, from the contractor who tests the site's hydrants.

    flowtest status
    flowtest submit < plan.json

`flowtest status` reports whether the order has been placed and what was ordered. `flowtest submit` reads the
plan on standard input and places the order. **The order can be placed only once.** It cannot be changed, extended
or replaced afterwards, and no result is known before it is placed.

The plan names one riser and one flow:

    {"riser": "SR05", "flow_gpm": 600}

## The test

The contractor connects hoses and a flow meter to the riser's test header, which is above the riser's alarm valve,
and sets the flow named in the plan, between %(lo).0f and %(hi).0f gpm. Nothing else flows on the site. The test is
run on %(day)s.

The report gives, all with the flow steady: the flow on the contractor's meter; the riser's supply gauge and its
serial; the contractor's own test gauge on the lead-in's flange tapping, just before the riser's control valve,
already referred to the site datum; and the reading of the utility's transmitter PT-0. The meter is good to about
0.3 per cent and the contractor's gauge repeats as the site's do. The report is written to `/app/flowtest/`.
""" % dict(lo=S.FLOW_TEST_RANGE[0], hi=S.FLOW_TEST_RANGE[1], day=S.FLOW_TEST_AT.strftime("%Y-%m-%d"))


EXAMPLE_NOTE = """# About this riser

SR00 served building E until the building was taken down at the end of 2022. Its records for that year are here
in the formats of the site's present records: its register row, its rows of the monthly round, the utility's
record of the main's pressure for the year, its maintenance log, which has no entry, and its gauge's certificate.

The round of 2022 took in SR00 along with the site's other risers.

No rating is given for it.
"""


def certificates(serials, zero):
    out = ["# Gauge certificates", "",
           "Each gauge was compared with the calibration laboratory's reference at three pressures. The error is "
           "the gauge's indication minus the reference, in psi.", "",
           "| serial | certificate | error at 40 psi | error at 60 psi | error at 80 psi |", "|---|---|---|---|---|"]
    for i, s in enumerate(serials):
        e = zero[s]
        out.append("| %s | CL-%d | %+.1f | %+.1f | %+.1f |" % (s, 60411 + 37 * i, e, e, e))
    return "\n".join(out) + "\n"


def documents():
    return {"fp12_supply_rating.md": standard(), "site_data.md": site_data(), "records_format.md": records_format(),
            "audit_note.md": audit_note(), "flow_test_order.md": order()}
