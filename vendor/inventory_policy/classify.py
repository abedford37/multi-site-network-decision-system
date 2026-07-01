"""ABC classification and SKU strategy label.

ABC is by demand volume on the classic Pareto split: the high-volume head is A,
the middle is B, the long tail is C. Service-level targets attach by class, so the
target is an explicit business decision rather than a hidden multiplier.
"""
from __future__ import annotations

import numpy as np

DEFAULT_SERVICE = {"A": 0.98, "B": 0.95, "C": 0.90}


def abc_classify(items, a_cut=0.80, b_cut=0.95, service=None):
    service = service or DEFAULT_SERVICE
    df = items.sort_values("weekly_mean", ascending=False).copy()
    share = df["weekly_mean"].cumsum() / df["weekly_mean"].sum()
    df["abc"] = np.where(share <= a_cut, "A", np.where(share <= b_cut, "B", "C"))
    df["service_level"] = df["abc"].map(service)
    return df.sort_index()


def sku_strategy(abc, pattern):
    return f"{abc}-{pattern}"
