"""Walk-forward evaluation.

Time series are evaluated by walking forward in time, never by a random split:
the model is trained only on the past and scored on the next unseen week, which
is how it will be used. We report MAE, WMAPE (scale-free), bias (over or under
forecasting), and skill against a naive last-week baseline, because a single
error number hides whether a method is biased or merely beating nothing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .pipeline import DemandForecaster


def walk_forward(demand, items, horizon=4, **kw):
    max_week = int(demand["week_index"].max())
    test_weeks = list(range(max_week - horizon + 1, max_week + 1))
    out = []
    for t in test_weeks:
        f = DemandForecaster(**kw).fit(demand[demand["week_index"] < t], items)
        pred = f.predict_week(demand[demand["week_index"] < t], items, t)
        actual = demand[demand["week_index"] == t][["item_id", "demand"]].rename(columns={"demand": "y_true"})
        naive = demand[demand["week_index"] == t - 1][["item_id", "demand"]].rename(columns={"demand": "y_naive"})
        fold = pred.merge(actual, on="item_id").merge(naive, on="item_id", how="left")
        fold["week_index"] = t
        out.append(fold)
    return pd.concat(out, ignore_index=True).dropna(subset=["y_true"])


def _scores(df):
    e = df["y_pred"] - df["y_true"]
    mae = e.abs().mean()
    wmape = e.abs().sum() / max(df["y_true"].sum(), 1e-9)
    bias = e.mean()
    naive_mae = (df["y_naive"] - df["y_true"]).abs().mean()
    skill = mae / naive_mae if naive_mae and not np.isnan(naive_mae) else np.nan
    return pd.Series({"n": len(df), "MAE": mae, "WMAPE": wmape, "bias": bias,
                      "skill_vs_naive": skill})


def metrics(pred):
    by_bucket = pred.groupby("bucket").apply(_scores, include_groups=False)
    overall = _scores(pred).to_frame("ALL").T
    return pd.concat([by_bucket, overall]).round(3)
