"""Measure the service level each policy actually delivers.

For every item we simulate many lead-time-demand outcomes from its true process
and count how often the reorder point (MIN) covers demand. That realized service
is compared to the item's target. Safety stock held is the reorder point above
mean lead-time demand, a proxy for working capital. The comparison is the point:
a correct policy should hit its target across patterns and place its capital where
the uncertainty is.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .sim import sample_ltd


def realized_service(items, policy, n=6000, seed=99):
    rng = np.random.default_rng(seed)
    mins = dict(zip(policy.item_id, policy.min_qty))
    rows = []
    for r in items.itertuples():
        ltd = sample_ltd(r.pattern, r.daily_mean, r.lead_time_days, r.lead_time_std, rng, n)
        rows.append({"item_id": r.item_id, "abc": r.abc, "pattern": r.pattern,
                     "origin": r.origin, "target": r.service_level,
                     "realized": float((ltd <= mins[r.item_id]).mean()),
                     "safety_stock": max(0.0, mins[r.item_id] - r.lead_time_days * r.daily_mean),
                     "cv": r.daily_std / r.daily_mean if r.daily_mean else 0.0})
    return pd.DataFrame(rows)


def summarize(df):
    gap = (df["realized"] - df["target"]).abs()
    return {"mean_realized": round(df["realized"].mean(), 3),
            "service_spread_std": round(df["realized"].std(), 3),
            "mean_abs_gap_to_target": round(gap.mean(), 3),
            "pct_below_target_by_5pts": round(float((df["realized"] < df["target"] - 0.05).mean()), 3),
            "total_safety_stock": round(df["safety_stock"].sum(), 0)}


def compare(items, faithful, improved):
    f = realized_service(items, faithful)
    im = realized_service(items, improved)
    tbl = pd.DataFrame({"faithful": summarize(f), "improved": summarize(im)}).T
    return tbl, f, im
