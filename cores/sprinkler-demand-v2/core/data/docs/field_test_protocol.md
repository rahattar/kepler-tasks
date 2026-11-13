# The field test protocol

The program asks for its system's field test (FP-7 section 6) on its standard output and receives the report on
its standard input.

To ask, the program writes one line to standard output:

    TEST {"outlet": "<outlet id>", "flow_gpm": <flow>, "gauges": ["<gauge port>", "<gauge port>"]}

and flushes it. The flow is between 10 and 2000 gpm; the two gauge ports are different ports of the package's
`gauge_ports`. One line comes back on standard input, a JSON object, either the report (the figures here are
illustrative):

    {"outlet": "FC-A", "flow_gpm": 600.0,
     "base_of_riser": {"static_psi": 92.4, "flowing_psi": 81.7},
     "gauges": {"A7": {"static_psi": 80.3, "flowing_psi": 66.1},
                "A14": {"static_psi": 80.2, "flowing_psi": 58.9}}}

or a refusal, `{"refused": "<reason>"}`. A system has one field test: a refused test counts as made, and any
further request is refused.

Every other line the program writes to standard output is ignored; diagnostics belong on standard error. A
program need not ask for a test. The results are written to the output file named on the command line.
