"""The shared catalog: one item universe that flows through every engine.

This is the single source of truth. It holds static master data only: each item's
demand history, physical attributes, supplier lead time, and demand geography, plus
the network of buildings. Operational positions that depend on upstream decisions,
on-hand by location, today's orders, and inbound containers, are synthesized later in
the adapters from the engines' outputs, so the catalog never bakes in a decision.

The network is two forward buildings and a reserve, named FWD-A, FWD-B, and STORAGE,
the naming every engine already shares. Item ids are IT-0001 upward across the whole
system, so a row means the same item in all five engines.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PATTERNS = ["smooth", "erratic", "intermittent", "lumpy"]
CATEGORIES = ["skincare", "devices", "consumables", "retail"]


def _series(pattern, weeks, rng):
    if pattern == "smooth":
        lvl = rng.uniform(20, 90)
        y = np.maximum(0, rng.normal(lvl, lvl * 0.15, weeks))
    elif pattern == "erratic":
        lvl = rng.uniform(15, 70)
        y = np.maximum(0, rng.normal(lvl, lvl * 0.6, weeks))
    elif pattern == "intermittent":
        lvl = rng.uniform(10, 50)
        occ = rng.random(weeks) < 0.4
        y = np.where(occ, rng.normal(lvl, lvl * 0.2, weeks), 0.0)
    else:  # lumpy
        lvl = rng.uniform(10, 60)
        occ = rng.random(weeks) < 0.35
        y = np.where(occ, np.maximum(0, rng.normal(lvl, lvl * 0.9, weeks)), 0.0)
    return np.maximum(0, y)


def generate(n_items=120, weeks=52, n_regions=7, seed=42):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2024-01-01")
    dates = [start + pd.Timedelta(weeks=int(w)) for w in range(weeks)]

    # geography: regions on a plane, each item concentrates demand near one region
    anchors = np.array([[20, 25], [75, 20], [30, 78], [80, 75], [50, 50], [20, 60], [70, 50]])
    anchors = anchors[:n_regions]
    coords = np.clip(anchors + rng.uniform(-8, 8, (n_regions, 2)), 5, 95)
    regions = pd.DataFrame({"region": [f"R{i+1}" for i in range(n_regions)],
                            "x": coords[:, 0], "y": coords[:, 1], "size": rng.uniform(0.7, 1.6, n_regions)})
    reg_xy = regions[["x", "y"]].to_numpy()
    reg_w = (regions["size"] / regions["size"].sum()).to_numpy()

    # suppliers: five import, three domestic, drive lead time
    n_sup = 8
    sup = []
    for i in range(n_sup):
        if i < 5:
            lt, lts, origin = rng.uniform(45, 75), rng.uniform(8, 20), "import"
        else:
            lt, lts, origin = rng.uniform(7, 16), rng.uniform(1.5, 4), "domestic"
        sup.append({"supplier_id": f"S{i+1:02d}", "origin": origin,
                    "lead_time_days": round(float(lt), 1), "lead_time_std": round(float(lts), 1)})
    suppliers = pd.DataFrame(sup)

    meta, drows, shares = [], [], []
    for i in range(1, n_items + 1):
        it = f"IT-{i:04d}"
        primary = int(rng.choice(n_regions, p=reg_w))
        prox = np.exp(-np.sqrt(((reg_xy - reg_xy[primary]) ** 2).sum(axis=1)) / 25.0)
        prox[primary] *= rng.uniform(3.0, 6.0)
        shares.append(prox / prox.sum())

        pattern = str(rng.choice(PATTERNS, p=[0.40, 0.25, 0.20, 0.15]))
        y = _series(pattern, weeks, rng)
        life = rng.random()
        if life < 0.08:                                   # never sold: no history at all
            y = np.full(weeks, np.nan)
            lifecycle = "never_sold"
        elif life < 0.20:                                 # sold before, nothing lately: dead
            y[weeks - 26:] = 0.0
            lifecycle = "dead"
        else:
            lifecycle = "live"

        size = str(rng.choice(["small", "medium", "large"], p=[0.45, 0.3, 0.25]))
        cube = float({"small": rng.uniform(0.01, 0.05), "medium": rng.uniform(0.05, 0.15),
                      "large": rng.uniform(0.15, 0.4)}[size])
        s = suppliers.iloc[int(rng.integers(0, n_sup))]
        meta.append({"item_id": it, "group": f"G{rng.integers(0, 6)}", "category": str(rng.choice(CATEGORIES)),
                     "price": round(float(rng.uniform(1.5, 40.0)), 2), "latent_pattern": pattern,
                     "lifecycle": lifecycle, "size": size, "parcel": bool(rng.random() < 0.6),
                     "weight": round(float(rng.uniform(0.2, 25.0)), 2), "cbm_per_unit": round(cube, 3),
                     "pack_size": int(rng.choice([1, 2, 6, 12, 24])), "moq": int(rng.choice([0, 10, 20, 50])),
                     "supplier_id": s.supplier_id, "origin": s.origin,
                     "lead_time_days": s.lead_time_days, "lead_time_std": s.lead_time_std,
                     "primary_region": regions.loc[primary, "region"]})
        for w in range(weeks):
            drows.append({"item_id": it, "week_index": w, "date": dates[w], "demand": y[w]})

    network = pd.DataFrame([
        {"building": "FWD-A", "role": "forward", "x": 28.0, "y": 30.0, "handling": 1.00},
        {"building": "FWD-B", "role": "forward", "x": 74.0, "y": 68.0, "handling": 1.08},
        {"building": "STORAGE", "role": "storage", "x": 50.0, "y": 50.0, "handling": 1.60},
    ])
    return {"items": pd.DataFrame(meta), "demand": pd.DataFrame(drows), "suppliers": suppliers,
            "regions": regions, "shares": np.array(shares), "network": network, "weeks": weeks}
