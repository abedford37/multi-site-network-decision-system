"""Evaluation: does optimizing beat unloading in arrival order?

The value of the engine is the demand it covers per scarce unload slot. We compare
the greedy demand-first optimizer against a first-come (earliest ETA) baseline that
uses the same daily capacity but ignores demand value when choosing. Coverage is
measured at the service level, so both are judged on the same probabilistic target.
"""
from __future__ import annotations

import pandas as pd

from .demand import required_table
from .optimize import schedule


def _summary(data, res, required):
    covered = res.required_total - sum(res.remaining.values())
    return {
        "coverage_rate": covered / res.required_total if res.required_total else 0.0,
        "covered_units": covered,
        "containers_used": len(res.assignments),
        "deferred": len(res.deferred),
        "visitor_units": sum(res.visitors.values()),
        "demurrage_cost": round(res.demurrage_cost, 0),
        "deadline_violations": len(res.violations),
    }


def evaluate(data, service_level=0.95):
    required = required_table(data["demand"], service_level)
    rows = {}
    for strat in ("greedy", "fifo"):
        res = schedule(data, required, strat)
        rows[strat] = _summary(data, res, required)
    df = pd.DataFrame(rows).T
    df["coverage_rate"] = df["coverage_rate"].round(3)
    df["lift_vs_fifo"] = (df["coverage_rate"] / df.loc["fifo", "coverage_rate"]).round(3)
    return df


def coverage_by_building(data, service_level=0.95, strategy="greedy"):
    required = required_table(data["demand"], service_level)
    res = schedule(data, required, strategy)
    home = dict(zip(data["items"].item_id, data["items"].home))
    req_b, rem_b = {}, {}
    for item, r in required.items():
        b = home[item]
        req_b[b] = req_b.get(b, 0.0) + r
        rem_b[b] = rem_b.get(b, 0.0) + res.remaining.get(item, 0.0)
    df = pd.DataFrame({
        "required": pd.Series(req_b),
        "covered": pd.Series({b: req_b[b] - rem_b[b] for b in req_b}),
    })
    df["rate"] = (df["covered"] / df["required"]).round(3)
    df["required"] = df["required"].round(0)
    df["covered"] = df["covered"].round(0)
    return df
