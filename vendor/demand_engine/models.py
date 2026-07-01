"""Forecasting methods, one per routing decision.

Why these and not one model for everything: a single regressor trained on
sparse, zero-heavy series learns to predict near zero and misses the spikes,
while intermittent-demand methods estimate the demand rate directly. Matching
the method to the demand pattern is the whole point of the SBC classification.
"""
from __future__ import annotations

import numpy as np
from xgboost import XGBRegressor


def croston(y, alpha=0.1):
    """Croston's method: smooth demand size and interval separately, forecast
    the per-period rate as size / interval. Built for intermittent demand."""
    y = np.asarray(y, dtype=float)
    y = np.nan_to_num(y, nan=0.0)
    nz = np.flatnonzero(y)
    if len(nz) == 0:
        return 0.0
    z = float(y[nz[0]])      # demand size estimate
    x = float(nz[1] - nz[0]) if len(nz) >= 2 else float(nz[0] + 1)  # interval estimate
    gap = 1
    for t in range(nz[0] + 1, len(y)):
        if y[t] > 0:
            z += alpha * (y[t] - z)
            x += alpha * (gap - x)
            gap = 1
        else:
            gap += 1
    return z / x if x > 0 else 0.0


def sba(y, alpha=0.1):
    """Syntetos-Boylan Approximation: Croston with a bias correction. Preferred
    over raw Croston for intermittent and lumpy demand (Syntetos and Boylan 2005)."""
    return (1.0 - alpha / 2.0) * croston(y, alpha)


class GlobalML:
    """One gradient-boosted model pooled across many items. A global model shares
    statistical strength across the catalog, which matters when each item has
    little history (Januschowski et al. 2020)."""

    def __init__(self, random_state=42):
        self.model = XGBRegressor(
            n_estimators=400, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
            objective="reg:squarederror", random_state=random_state,
            early_stopping_rounds=30, eval_metric="mae")

    def fit(self, X, y):
        n = len(X)
        cut = max(1, int(n * 0.85))
        self.model.fit(X.iloc[:cut], y.iloc[:cut],
                       eval_set=[(X.iloc[cut:], y.iloc[cut:])], verbose=False)
        return self

    def predict(self, X):
        return np.clip(self.model.predict(X), 0, None)
