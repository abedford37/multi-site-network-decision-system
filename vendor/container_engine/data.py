"""Synthetic network generator.

Produces items with attributes and a home building, a per-item demand forecast
(mean and standard deviation), and inbound containers with ETAs and cubic volume.
Containers are built mostly coherent to one building with some impurity, so the
visitor and mixed-container behavior is exercised. Reproducible via seed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .assign_home import assign_homes
from .nodes import DEFAULT_FORWARD

SIZES = ["small", "medium", "large"]


def generate(n_items=120, n_containers=60, horizon=14, capacity=3, seed=42,
             buildings=None):
    rng = np.random.default_rng(seed)
    buildings = buildings or DEFAULT_FORWARD

    # Items and attributes
    items = []
    for i in range(1, n_items + 1):
        size = rng.choice(SIZES, p=[0.45, 0.3, 0.25])
        parcel = bool(rng.random() < (0.8 if size == "small" else 0.2))
        items.append({
            "item_id": f"IT-{i:04d}",
            "size": size,
            "parcel": parcel,
            "weight": round(float(rng.uniform(0.2, 25.0)), 2),
            "velocity": round(float(rng.uniform(0.1, 5.0)), 2),
            "cbm_per_unit": round(float({"small": rng.uniform(0.01, 0.05),
                                         "medium": rng.uniform(0.05, 0.15),
                                         "large": rng.uniform(0.15, 0.4)}[size]), 3),
        })
    items = assign_homes(pd.DataFrame(items), buildings)

    # Demand forecast per item
    mean = rng.uniform(20, 120, n_items)
    demand = pd.DataFrame({
        "item_id": items["item_id"],
        "mean": mean.round(1),
        "std": (mean * rng.uniform(0.1, 0.4, n_items)).round(1),
    })

    # Containers: pick a target building, fill mostly with its items plus impurity
    by_home = {b.name: items[items["home"] == b.name]["item_id"].tolist() for b in buildings}
    names = [b.name for b in buildings]
    cont_rows, content_rows = [], []
    for c in range(1, n_containers + 1):
        cid = f"CN-{c:04d}"
        target = rng.choice(names)
        others = [n for n in names if n != target]
        n_lines = int(rng.integers(5, 11))
        cbm = 0.0
        picked = set()
        for _ in range(n_lines):
            src = target if rng.random() < 0.8 else rng.choice(others)
            pool = by_home[src]
            if not pool:
                continue
            item = rng.choice(pool)
            if item in picked:
                continue
            picked.add(item)
            qty = int(rng.integers(10, 60))
            cpu = float(items.loc[items.item_id == item, "cbm_per_unit"].iloc[0])
            cbm += qty * cpu
            content_rows.append({"container_id": cid, "item_id": item, "qty": qty})
        eta = int(rng.integers(0, horizon))
        cont_rows.append({"container_id": cid, "eta_day": eta,
                          "cbm": round(cbm, 2),
                          "free_until": eta + 3,          # free storage through here
                          "deadline": eta + 9,            # hard must-unload-by day
                          "demurrage_per_day": round(float(rng.uniform(40, 150)), 2),
                          "target_hint": target})
    containers = pd.DataFrame(cont_rows)
    contents = pd.DataFrame(content_rows)
    return {"buildings": buildings, "items": items, "demand": demand,
            "containers": containers, "contents": contents,
            "capacity": capacity, "horizon": horizon}
