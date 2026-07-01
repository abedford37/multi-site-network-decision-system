"""Synthetic demand data generator.

Produces a reproducible dataset that contains every routing case (smooth,
erratic, intermittent, lumpy, and new cold-start items), with real calendar
dates, a grouping key, and item attributes. The generator assigns a latent
pattern, but the engine never sees that label: classification is derived from
the data, so the demo proves the classifier, it does not assume it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PATTERNS = ["smooth", "erratic", "intermittent", "lumpy", "new"]
CATEGORIES = ["ambient", "chilled", "seasonal", "promo"]


def _series(pattern, weeks, rng):
    t = np.arange(weeks)
    season = 1.0 + 0.25 * np.sin(2 * np.pi * t / 52.0)
    if pattern == "smooth":
        base = rng.uniform(20, 60)
        y = base * season * rng.normal(1.0, 0.10, weeks)
    elif pattern == "erratic":
        base = rng.uniform(15, 50)
        y = base * season * rng.lognormal(0.0, 0.75, weeks)  # CV2 ~ 0.75 > 0.49 cut
    elif pattern == "intermittent":
        rate = rng.uniform(0.25, 0.45)
        size = rng.uniform(8, 20)
        y = np.where(rng.random(weeks) < rate, rng.normal(size, size * 0.15, weeks), 0.0)
    elif pattern == "lumpy":
        rate = rng.uniform(0.2, 0.4)
        y = np.where(rng.random(weeks) < rate, rng.lognormal(2.2, 0.9, weeks), 0.0)
    else:  # new: only the tail exists, rest missing
        full = _series("smooth", weeks, rng)
        cut = weeks - rng.integers(4, 8)
        full[:cut] = np.nan
        return full
    return np.clip(y, 0, None)


def generate(n_per_pattern=45, weeks=52, n_groups=6, seed=42):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2024-01-01")
    dates = [start + pd.Timedelta(weeks=int(w)) for w in range(weeks)]
    rows, items = [], []
    iid = 0
    for pattern in PATTERNS:
        for _ in range(n_per_pattern):
            iid += 1
            item = f"SKU-{iid:04d}"
            group = f"G{rng.integers(0, n_groups)}"
            cat = rng.choice(CATEGORIES)
            price = round(float(rng.uniform(1.5, 40.0)), 2)
            items.append({"item_id": item, "group": group, "category": cat,
                          "price": price, "latent_pattern": pattern})
            y = _series(pattern, weeks, rng)
            for w in range(weeks):
                rows.append({"item_id": item, "week_index": w, "date": dates[w],
                             "demand": y[w]})
    demand = pd.DataFrame(rows)
    items_df = pd.DataFrame(items)
    return demand, items_df
