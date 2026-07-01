"""Feature construction for the machine-learning route.

Every feature for a target week t uses only information available before t: lags
and rolling statistics of the item, the group's mean demand in the prior week,
the known calendar, and static attributes. Nothing contemporaneous with t enters
the row, which is the difference between an honest backtest and an inflated one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = (1, 2, 3, 4)
ROLL = 4


def make_supervised(demand, items, target_weeks):
    """One row per (item, target_week) with leakage-free features and realized y."""
    d = demand.merge(items[["item_id", "group", "category", "price"]], on="item_id")
    d = d.sort_values(["item_id", "week_index"])
    g = d.groupby("item_id")["demand"]
    for L in LAGS:
        d[f"lag{L}"] = g.shift(L)
    # Rolling stats via transform so the result stays aligned to d's index. A
    # reset_index here would misalign the values against the sorted frame and
    # silently produce NaN at serve time, where roll_mean matters most.
    d["roll_mean"] = g.transform(lambda x: x.shift(1).rolling(ROLL).mean())
    d["roll_std"] = g.transform(lambda x: x.shift(1).rolling(ROLL).std())

    # Group mean demand in the PRIOR week (available at serve time, no leakage).
    gm = (d.groupby(["group", "week_index"])["demand"].mean()
          .reset_index().rename(columns={"demand": "gmean"}).sort_values(["group", "week_index"]))
    gm["group_prev_mean"] = gm.groupby("group")["gmean"].shift(1)
    d = d.merge(gm[["group", "week_index", "group_prev_mean"]], on=["group", "week_index"], how="left")

    woy = pd.to_datetime(d["date"]).dt.isocalendar().week.astype("float")
    d["woy_sin"] = np.sin(2 * np.pi * woy / 52.0)
    d["woy_cos"] = np.cos(2 * np.pi * woy / 52.0)
    d["trend"] = d["week_index"]
    cat = pd.get_dummies(d["category"], prefix="cat")
    d = pd.concat([d, cat], axis=1)

    feat_cols = ([f"lag{L}" for L in LAGS] + ["roll_mean", "roll_std", "group_prev_mean",
                 "woy_sin", "woy_cos", "trend", "price"] + list(cat.columns))
    rows = d[d["week_index"].isin(target_weeks)].dropna(subset=[f"lag{L}" for L in LAGS])
    return rows, feat_cols
