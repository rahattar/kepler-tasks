"""A correct but unoptimised version of ref_rerate.py, for the time limit: no linearised ranking. Every
candidate (each registered C, each valve, each pair of ports, each run's flow) is refitted in full, every
network solve from a cold start. It reaches the reference's answers; it does not reach them inside the limit.

    python3 naive_rerate.py PACKAGE_DIR OUT_JSON
"""
import itertools
import sys

import ref_rerate as R


class Plain(R.Campaign):
    def drops(self, var, x):
        self.q0 = {}                                     # every solve from scratch
        return super().drops(var, x)

    def rank(self):
        S = self.S
        out = [(0.0, ("C", i)) for i in range(len(S.groups)) if ("C", i) not in self.var]
        out += [(0.0, ("valve", i)) for i in S.valve_pipes if ("valve", i) not in self.var]
        if self.swap is None:
            out += [(0.0, ("swap", p)) for p in itertools.combinations(range(1, len(self.g)), 2)]
        if self.flow_run is None:
            out += [(0.0, ("flow", k)) for k, _n, _q in self.flowing]
        return out

    def settle(self, top=3, depth=3):
        return super().settle(top=10 ** 6, depth=depth)


if __name__ == "__main__":
    R.Campaign = Plain
    R.main(sys.argv[1], sys.argv[2])
