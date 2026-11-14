"""The sealed definition: what happens to a hoist rope, element by element.

A rope is a row of elements, one to a survey station, numbered here as they lie at the end of the log, from the
drum anchorage. `life` takes one crane's reeving and its true movement log and follows every element through the
log as a piece of material:

  - an element is bent once when a sheave's point of touch passes it (RS-4 sections 1 and 2), at the tension of
    that movement (section 3), and each bending takes w / N of its life (sections 4 and 5), N reckoned with the
    diameter the element was measured at in the last survey before the movement;
  - where the rope was turned end for end on a given day, an element that lies x from the drum anchorage at the
    end lay L - x from it before that day, and was bent there;
  - at each survey day the element's diameter is read with a gauge. A rope thins with the damage its elements
    have taken, each rope by constants of its own and each element by a gain of its own, and a little all along
    its length with time (`Wear`).

Nothing here reads a package, and nothing here knows how a survey was written down: `life` returns the damage of
every element at the end of the log and the diameter of every element at every survey, in element order.
works.py writes the packages from that. The results the verifier holds are these damages, never the output of a
program that reads a package.
"""
import numpy as np

G = 9.80665
# construction -> b0, b1, b2, b3 of RS-4 section 4
ROPE = {"8x36": (-1.214, 0.887, 7.432, -2.103), "6x36": (-1.371, 0.934, 7.518, -2.146)}
CALIPER_MM = 0.012          # repeatability of a gauge reading, one standard deviation


def endurance(S, D, d, construction):
    """Bendings to failure of an element of diameter d (mm) over a sheave of diameter D (mm) at tension S (N)."""
    b0, b1, b2, b3 = ROPE[construction]
    r = np.log10(D / d)
    return 10.0 ** (b0 + (b1 + b3 * r) * np.log10(S / d ** 2) + b2 * r)


class Wear:
    """How one rope's diameter follows what its elements have been through."""

    def __init__(self, rng, elements):
        self.rate = rng.uniform(0.034, 0.062)          # share of the diameter lost at the rope's reference damage
        self.power = rng.uniform(0.55, 0.9)
        self.drift = rng.uniform(0.007, 0.016)         # share lost all along the rope over the whole log
        smooth = np.convolve(rng.standard_normal(elements + 4), np.ones(3) / 3 ** 0.5, "same")[2:-2]
        self.gain = np.exp(0.16 * (0.7 * smooth + 0.7 * rng.standard_normal(elements)))
        self.rng = rng

    def new(self, nominal, elements):
        return np.round(nominal * (1 + 0.0004 * self.rng.standard_normal(elements)), 2)

    def read(self, nominal, damage, reference, share_of_log):
        true = nominal * (1 - self.drift * share_of_log - self.rate * self.gain * (damage / reference) ** self.power)
        return np.round(true + CALIPER_MM * self.rng.standard_normal(damage.size), 2)


def life(crane, log, survey_days, last_day, turn_day, wear_seed, reference=None):
    """(damage of each element at the end of the log, [diameter of each element at each survey]).

    crane: dict with L, H, falls, block, eff, construction, d (nominal diameter), spacing and sheaves, each
    sheave a dict with parts, offset, D, weight. log: array of rows (day, from height, to height, hook load in
    t), as the controller writes them. turn_day: the day the rope was turned end for end, or None.
    reference: the damage at which the rope has lost `rate` of its diameter; None takes the rope's own greatest
    damage, found by a first pass.
    """
    if reference is None:
        first, _ = life(crane, log, survey_days, last_day, turn_day, wear_seed, reference=1.0)
        reference = float(first.max())
    L, H = crane["L"], crane["H"]
    count = int(round(L / crane["spacing"]))
    x_end = crane["spacing"] * (0.5 + np.arange(count))            # where each element lies at the end
    x_start = L - x_end if turn_day is not None else x_end         # and where it lay before the turn
    day, h_from, h_to, load = log.T
    tension = (load + crane["block"]) * 1e3 * G / (crane["falls"] * crane["eff"])
    low, high = np.minimum(h_from, h_to), np.maximum(h_from, h_to)
    before_turn = day < turn_day if turn_day is not None else np.zeros(day.size, bool)
    wear = Wear(np.random.default_rng(wear_seed), count)
    damage = np.zeros(count)
    readings = []
    edges = list(survey_days) + [np.inf]
    diameter = None
    for k in range(len(survey_days)):
        diameter = wear.new(crane["d"], count) if k == 0 else wear.read(crane["d"], damage, reference, survey_days[k] / last_day)
        readings.append(diameter.copy())
        in_epoch = (day >= edges[k]) & (day < edges[k + 1])
        for sheave in crane["sheaves"]:
            for was_before, place in ((True, x_start), (False, x_end)):
                chosen = in_epoch & (before_turn == was_before)
                if not chosen.any():
                    continue
                # hook height at which this sheave's point of touch is on the element
                meets = H - (L - sheave["offset"] - place) / sheave["parts"]
                passed = (low[chosen][:, None] < meets[None, :]) & (meets[None, :] <= high[chosen][:, None])
                N = endurance(tension[chosen][:, None], sheave["D"], diameter[None, :], crane["construction"])
                damage += sheave["weight"] * (passed / N).sum(0)
    return damage, readings
