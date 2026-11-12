#!/usr/bin/env python3
"""A second solution, written separately from solution/solve.py and sharing no code with it.

    python3 independent.py

It reads the records as pandas tables and does the arithmetic on whole columns. Where AP-12 leaves a choice it
takes its own: the cold line by a straight-line fit through the two reading planes, a model's 2019 ratio as the
median of its pumps' ratios, two models taken as one group when their ratios differ by less than three times
what one degree of survey reading is worth, and the last train of each group visited where the reference
visits the first. Its sheet is graded by the verifier's module, on the shipped records and on the laboratory
seeds 5301 to 5320, and set beside the reference's.
"""
import os
import re
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

import common

ALPHA = 11.5e-6
BASE = 25.0


def tables(folder):
    names = ("train_register", "pump_data", "dial_sheets", "tool_crib_log", "sag_cards",
             "support_temperature_survey", "process_conditions", "gearbox_running_position", "hot_checks",
             "work_orders")
    return {n: pd.read_csv(os.path.join(folder, n + ".csv")) for n in names}


def second_sheet(folder, seed):
    t = tables(folder)
    text = {n: open(os.path.join(folder, "docs", n + ".md")).read()
            for n in ("alignment_procedure", "kit_leaflets", "laser_service")}
    tol = float(re.findall(r"(\d\.\d+) mm of the stationary", text["alignment_procedure"])[0])
    edges = sorted({float(v) for v in re.findall(r"up to (\d+) mm", text["kit_leaflets"])})

    # one row a train, everything joined on
    df = t["train_register"].merge(t["dial_sheets"], on="tag").merge(t["support_temperature_survey"], on="tag")
    df = df.merge(t["process_conditions"].rename(columns={"pumped_temperature_C": "pumped_now"})[["tag", "pumped_now"]],
                  on="tag", how="left")
    crib = t["tool_crib_log"]
    held = df[["tag", "fitter", "date"]].merge(crib, left_on="fitter", right_on="issued_to")
    held = held[(held["out"] <= held["date"]) & (held["date"] <= held["returned"])]
    assert held["tag"].is_unique and len(held) == len(df)
    df = df.merge(held[["tag", "kit"]], on="tag")
    df["bar_set"] = np.searchsorted(edges, df["span_mm"].to_numpy(), side="left") + 1
    df = df.merge(t["sag_cards"], on=["kit", "bar_set"])
    df = df.set_index("tag").sort_index()
    sag = df["mandrel_bottom_reading_mm"]

    # cold offsets at the two planes: x = 0 at the stationary hub, x = span at the movable hub
    y0 = (df["MS_bottom"] - sag) / 2.0
    y1 = -(df["SM_bottom"] - sag) / 2.0
    z0 = (df["MS_left"] - df["MS_right"]) / 2.0
    z1 = (df["SM_right"] - df["SM_left"]) / 2.0

    parts = df["stationary_machine"].str.split(" ", n=1, expand=True)
    df["kind"], df["model"] = parts[0], parts[1]
    pumps = df[df["kind"] == "pump"].copy()
    pumps["ratio19"] = (pumps["stationary_support_C"] - BASE) / (pumps["pumped_temperature_C"] - BASE)
    by_model = pumps.groupby("model")["ratio19"].median()

    orders = t["work_orders"]
    work = {tag: "lagged" if words.str.contains("lagged").any() else "blanked" if words.str.contains("blanked").any() else ""
            for tag, words in orders.groupby("item")["work"]}
    pumps["work"] = [work.get(tag, "") for tag in pumps.index]
    build = t["pump_data"].set_index("model")
    pumps["label"] = [("%s/%s/%s" % (build.loc[m, "casing_support"], build.loc[m, "bearing_pedestal"], w)) if w else ""
                      for m, w in zip(pumps["model"], pumps["work"])]

    # groups: within a label, models whose 2019 ratios cannot be told apart by the survey's own reading
    groups = []
    for label, block in pumps[pumps["label"] != ""].groupby("label"):
        one_degree = 1.0 / (block["pumped_temperature_C"] - BASE).min()
        ordered = by_model[sorted(block["model"].unique())].sort_values()
        cluster = [ordered.index[0]]
        for model, ratio in list(ordered.items())[1:]:
            if ratio - by_model[cluster[-1]] > 3.0 * one_degree:
                groups.append(sorted(block.index[block["model"].isin(cluster)]))
                cluster = [model]
            else:
                cluster.append(model)
        groups.append(sorted(block.index[block["model"].isin(cluster)]))

    # turbines whose hot check has been followed by work on the exhaust or its supports
    turbines = []
    checks = t["hot_checks"].set_index("tag")
    for tag in df.index[df["movable_machine"] == "steam turbine"]:
        later = orders[(orders["item"] == tag) & (orders["date"] > checks.loc[tag, "date"])]
        if later["work"].str.contains("expansion joint|support|piping", case=False).any():
            turbines.append(tag)

    visits = turbines + [group[-1] for group in groups]
    assert len(visits) == int(re.findall(r"time for (\d+) trains", text["laser_service"])[0])
    seen = pd.DataFrame(common.reports(seed, visits)).T

    # support temperature of every pump as the unit now runs
    ratio = pumps["model"].map(by_model)
    for group in groups:
        tag = [g for g in group if g in seen.index][0]
        support = df.loc[tag, "ambient_C"] + seen.loc[tag, "stationary_rise"] / (ALPHA * df.loc[tag, "stationary_shaft_height_mm"])
        ratio[group] = (support - BASE) / (df.loc[tag, "pumped_now"] - BASE)
    support_now = df["stationary_support_C"].astype(float).copy()
    support_now[pumps.index] = BASE + ratio * (pumps["pumped_now"] - BASE)

    s_rise = ALPHA * df["stationary_shaft_height_mm"] * (support_now - df["ambient_C"])
    s_side = pd.Series(0.0, index=df.index)
    gear = t["gearbox_running_position"].set_index("model")
    for tag in df.index[df["kind"] == "gearbox"]:
        s_rise[tag] = gear.loc[df.loc[tag, "model"], "rise_mm"]
        s_side[tag] = gear.loc[df.loc[tag, "model"], "lateral_to_right_mm"]
    m_rise = ALPHA * df["movable_shaft_height_mm"] * (df["movable_support_C"] - df["ambient_C"])
    m_side = pd.Series(0.0, index=df.index)
    for tag in df.index[df["movable_machine"] == "steam turbine"]:
        if tag not in seen.index:
            m_rise[tag], m_side[tag] = checks.loc[tag, "rise_mm"], checks.loc[tag, "lateral_mm"]
    for tag in seen.index:
        y0[tag], y1[tag] = seen.loc[tag, "y_stationary_plane"], seen.loc[tag, "y_movable_plane"]
        z0[tag], z1[tag] = seen.loc[tag, "z_stationary_plane"], seen.loc[tag, "z_movable_plane"]
        s_rise[tag], s_side[tag] = seen.loc[tag, "stationary_rise"], seen.loc[tag, "stationary_lateral"]
        m_rise[tag], m_side[tag] = seen.loc[tag, "movable_rise"], seen.loc[tag, "movable_lateral"]

    sheet = {}
    for tag in df.index:
        span = float(df.loc[tag, "span_mm"])
        feet = span + float(df.loc[tag, "hub_plane_to_front_feet_mm"]) + np.array([0.0, float(df.loc[tag, "front_to_rear_feet_mm"])])
        row = []
        for a, b, grow in ((y0[tag], y1[tag], m_rise[tag] - s_rise[tag]), (z0[tag], z1[tag], m_side[tag] - s_side[tag])):
            slope, level = np.polyfit([0.0, span], [a, b], 1)
            row += list(-(level + slope * feet + grow))
        sheet[tag] = tuple(float(v) for v in row)
    return sheet, visits, tol


def main():
    sheet, visits, tol = second_sheet(common.DATA, common.SHIPPED)
    outcome = common.grade(sheet)
    reference, programme = common.run()
    gap = max(abs(a - b) for tag in sheet for a, b in zip(sheet[tag], reference[tag]))
    total = outcome.trains
    print("authoring/evidence/independent.py against the sealed definition, graded by tests/grade_moves.py.\n")
    print("its laser programme: %s" % " ".join(visits))
    print("the reference's:     %s" % " ".join(programme))
    print("\non the shipped records: %d of %d trains aligned, worst left %.4f mm against %.2f"
          % (outcome.aligned, total, max(abs(r["worst_mm"]) for r in outcome.detail.values()), tol))
    print("largest difference between its moves and the reference's, any foot of any train: %.4f mm" % gap)
    worst_count, far = total, 0.0
    for seed in common.LAB_SEEDS:
        box = tempfile.mkdtemp(prefix="sam_ind_")
        try:
            common.gen.main(box, seed)
            other, _, _ = second_sheet(box, seed)
        finally:
            shutil.rmtree(box, ignore_errors=True)
        graded = common.grade(other, seed)
        worst_count = min(worst_count, graded.aligned)
        far = max(far, max(abs(r["worst_mm"]) for r in graded.detail.values()))
    print("worst over %d laboratory seeds: %d of %d trains aligned, worst left %.4f mm"
          % (len(common.LAB_SEEDS), worst_count, total, far))
    return 0 if outcome.accepted and worst_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
