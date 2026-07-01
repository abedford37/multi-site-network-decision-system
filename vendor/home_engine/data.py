"""Synthetic slotting instance with a realistic demand-pattern spread.

Each item is generated with the raw signals the demand engine would report: whether it
has ever sold, its average demand interval and sale-size variability if it has, and its
mean demand. From those the classifier derives a demand-pattern bucket and a placement
class. Smooth and erratic items are active. Some intermittent and lumpy items are slow.
Items with history but no recent movement are dead. Items that have never sold are new,
and are placed forward on a provisional cold-start estimate rather than treated as dead.

Active and new items carry a footprint they need at a forward home, from OPHQ times
cube, provisional for new items. Slow and dead items carry only the leftover on-hand
sitting in storage. Forward capacity is sized so active and new footprint fills about
85 percent of the forward network. Reproducible via seed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .classify import classify_movement, FORWARD_CLASSES
from .nodes import default_locations
from .regions import distance_matrix


def generate(n_items=200, n_regions=7, seed=42):
    rng = np.random.default_rng(seed)
    anchors = np.array([[20, 25], [75, 20], [30, 78], [80, 75], [50, 50], [20, 60], [70, 50]])
    anchors = anchors[:n_regions] if n_regions <= len(anchors) else np.vstack(
        [anchors, rng.uniform(10, 90, (n_regions - len(anchors), 2))])
    coords = np.clip(anchors + rng.uniform(-8, 8, (n_regions, 2)), 5, 95)
    regions = pd.DataFrame({"region": [f"R{i+1}" for i in range(n_regions)],
                            "x": coords[:, 0], "y": coords[:, 1],
                            "size": rng.uniform(0.7, 1.6, n_regions)})
    reg_xy = regions[["x", "y"]].to_numpy()
    reg_w = (regions["size"] / regions["size"].sum()).to_numpy()

    rows, shares = [], []
    for i in range(1, n_items + 1):
        primary = rng.choice(n_regions, p=reg_w)
        prox = np.exp(-np.sqrt(((reg_xy - reg_xy[primary]) ** 2).sum(axis=1)) / 25.0)
        prox[primary] *= rng.uniform(3.0, 6.0)
        shares.append(prox / prox.sum())
        cube = float(rng.uniform(0.02, 0.25))

        u = rng.random()
        if u < 0.08:                                        # never sold: new item
            never_sold, adi, cv2, mean = True, np.nan, np.nan, np.nan
            demand = float(rng.uniform(5, 25))              # provisional cold-start estimate
            ophq = float(rng.uniform(40, 150))              # provisional policy
            fp_active, fp_storage = ophq * cube, 0.0
        else:
            never_sold = False
            adi = float(rng.uniform(1.0, 1.30) if rng.random() < 0.6 else rng.uniform(1.40, 3.2))
            cv2 = float(rng.uniform(0.05, 0.45) if rng.random() < 0.6 else rng.uniform(0.5, 1.8))
            base = float(rng.lognormal(3.0, 0.7))
            if adi >= 1.32:
                base *= float(rng.uniform(0.05, 0.5))       # sporadic items move less
            mean = 0.0 if rng.random() < 0.11 else base     # sold before, nothing lately: dead
            demand = mean
            ophq = float(rng.uniform(40, 260))              # active policy; cleared later if storage-bound
            fp_active = ophq * cube
            fp_storage = float(rng.uniform(5, 120)) * cube  # leftover on-hand if it lands in storage

        rows.append({"item_id": f"IT-{i:04d}", "never_sold": never_sold,
                     "adi": round(adi, 3) if adi == adi else np.nan,
                     "cv2": round(cv2, 3) if cv2 == cv2 else np.nan,
                     "mean_demand": round(mean, 2) if mean == mean else np.nan,
                     "demand": round(demand, 2), "cube": round(cube, 3),
                     "ophq": round(ophq, 1) if ophq == ophq else np.nan,
                     "footprint_active": round(fp_active, 2), "footprint_storage": round(fp_storage, 2),
                     "primary_region": regions.loc[primary, "region"]})

    items = pd.DataFrame(rows)
    cls = classify_movement(items)
    items = pd.concat([items, cls], axis=1)
    items["provisional"] = items["placement_class"] == "new"
    # footprint depends on placement: forward items use active footprint, storage items the leftover
    fwd_mask = items["placement_class"].isin(FORWARD_CLASSES)
    items["footprint"] = np.where(fwd_mask, items["footprint_active"], items["footprint_storage"])
    # clear policy for storage-bound items
    items.loc[~fwd_mask, "ophq"] = np.nan
    items = items.drop(columns=["footprint_active", "footprint_storage"])
    shares = np.array(shares)

    locations = default_locations()
    fwd_fp = items.loc[fwd_mask, "footprint"].sum()
    tail_fp = items.loc[~fwd_mask, "footprint"].sum()
    fwd_weights = np.array([0.30, 0.22, 0.26, 0.22])
    locations.loc[locations.role == "forward", "cube_capacity"] = np.round((fwd_fp / 0.85) * fwd_weights, 1)
    locations.loc[locations.role == "storage", "cube_capacity"] = round(tail_fp / 0.85, 1)

    return {"items": items, "locations": locations, "regions": regions, "shares": shares}


def forward_view(state):
    """Forward-eligible items (active and new) and forward buildings: the optimization's inputs."""
    items = state["items"]
    mask = items["placement_class"].isin(FORWARD_CLASSES).to_numpy()
    fwd = state["locations"][state["locations"].role == "forward"].reset_index(drop=True)
    dist = distance_matrix(fwd, state["regions"])
    return mask, items[mask].reset_index(drop=True), state["shares"][mask], fwd, dist
