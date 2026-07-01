"""Synthetic catalog: items with a demand pattern, a forecast (mean and standard
deviation), an assigned supplier with its lead time and lead-time variability, an
ABC class, and pack and MOQ rules. Import suppliers have longer and more variable
lead times than domestic ones, which is the whole reason lead-time variability
matters. Reproducible via seed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .classify import abc_classify
from .sim import PATTERNS, daily_stats


def generate(n_items=200, n_suppliers=8, seed=42, service=None):
    rng = np.random.default_rng(seed)

    sup = []
    n_import = n_suppliers * 5 // 8
    for i in range(n_suppliers):
        if i < n_import:
            lt_mean, lt_std, origin = rng.uniform(45, 75), rng.uniform(8, 20), "import"
        else:
            lt_mean, lt_std, origin = rng.uniform(7, 16), rng.uniform(1.5, 4), "domestic"
        sup.append({"supplier_id": f"S{i + 1:02d}", "origin": origin,
                    "lead_time_days": round(float(lt_mean), 1),
                    "lead_time_std": round(float(lt_std), 1)})
    suppliers = pd.DataFrame(sup)

    rows = []
    for i in range(n_items):
        pattern = rng.choice(PATTERNS, p=[0.40, 0.25, 0.20, 0.15])
        d = float(rng.lognormal(mean=3.2, sigma=1.0)) / 7          # daily base demand
        s = suppliers.iloc[int(rng.integers(0, n_suppliers))]
        dm, ds = daily_stats(pattern, d, rng)
        pack = int(rng.choice([1, 2, 6, 12, 24]))
        rows.append({"item_id": f"IT-{i + 1:04d}", "pattern": pattern,
                     "weekly_mean": round(dm * 7, 2), "weekly_std": round(ds * np.sqrt(7), 2),
                     "daily_mean": round(dm, 4), "daily_std": round(ds, 4),
                     "supplier_id": s.supplier_id, "lead_time_days": s.lead_time_days,
                     "lead_time_std": s.lead_time_std, "origin": s.origin,
                     "pack_size": pack, "moq": pack * int(rng.choice([1, 1, 2, 5]))})
    items = abc_classify(pd.DataFrame(rows), service=service)
    return {"items": items, "suppliers": suppliers}
