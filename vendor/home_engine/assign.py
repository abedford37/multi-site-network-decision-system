"""Assign homes. Slow and dead items are preassigned to storage with no policy and do
not touch forward cube. Active items are placed into forward buildings under cube
capacity to minimize total cost, via a regret-ordered greedy start and local search.

Regret is how much worse an item's second-best building is than its best, so placing
high-regret items first hands the scarce prime capacity to the items that would lose
the most by being displaced, which is velocity-aware since high-demand items carry the
largest cost gaps. Local search then applies capacity-respecting single moves and
pairwise swaps until no move lowers total cost. Fallback ranks are the next-best
forward buildings by cost, held as contingency targets for the downstream engines.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .cost import cost_matrix
from .data import forward_view


def _local_search(c, fp, cap, assign, max_pass=10):
    n_items, n_b = c.shape
    load = np.zeros(n_b)
    for i, b in enumerate(assign):
        load[b] += fp[i]
    for _ in range(max_pass):
        improved = False
        for i in range(n_items):
            b = assign[i]
            for b2 in range(n_b):
                if b2 != b and load[b2] + fp[i] <= cap[b2] and c[i, b2] < c[i, b] - 1e-9:
                    load[b] -= fp[i]; load[b2] += fp[i]; assign[i] = b2; b = b2
                    improved = True
        for i in range(n_items):
            for j in range(i + 1, n_items):
                bi, bj = assign[i], assign[j]
                if bi == bj:
                    continue
                if (c[i, bj] + c[j, bi]) - (c[i, bi] + c[j, bj]) < -1e-9:
                    ni, nj = load[bi] - fp[i] + fp[j], load[bj] - fp[j] + fp[i]
                    if ni <= cap[bi] and nj <= cap[bj]:
                        load[bi], load[bj] = ni, nj
                        assign[i], assign[j] = bj, bi
                        improved = True
        if not improved:
            break
    return assign, load


def assign_items(state, improve=True):
    mask, act, ashares, fwd, dist = forward_view(state)
    c = cost_matrix(state)
    fp = act["footprint"].to_numpy()
    names = fwd["building"].to_numpy()
    cap = fwd["cube_capacity"].to_numpy().astype(float)
    n_items = c.shape[0]

    order_cost = np.argsort(c, axis=1)
    regret = c[np.arange(n_items), order_cost[:, 1]] - c[np.arange(n_items), order_cost[:, 0]]
    order = np.argsort(-regret)

    remaining = cap.copy()
    assign = np.full(n_items, -1)
    overflow = []
    for i in order:
        placed = False
        for b in order_cost[i]:
            if remaining[b] >= fp[i]:
                assign[i] = b; remaining[b] -= fp[i]; placed = True
                break
        if not placed:
            b = int(np.argmax(remaining))
            assign[i] = b; remaining[b] -= fp[i]; overflow.append(int(i))

    load = _local_search(c, fp, cap, assign)[1] if improve else cap - remaining

    fallbacks = [([names[b] for b in order_cost[i] if b != assign[i]] + [None, None])[:2]
                 for i in range(n_items)]
    fwd_tbl = pd.DataFrame({
        "item_id": act["item_id"].to_numpy(), "movement_bucket": act["movement_bucket"].to_numpy(),
        "placement_class": act["placement_class"].to_numpy(), "provisional": act["provisional"].to_numpy(),
        "primary_region": act["primary_region"].to_numpy(), "footprint": act["footprint"].to_numpy(),
        "primary_home": names[assign], "home_2": [f[0] for f in fallbacks],
        "home_3": [f[1] for f in fallbacks], "cost": np.round(c[np.arange(n_items), assign], 1),
        "has_policy": True})

    tail = state["items"][~mask]
    tail_tbl = pd.DataFrame({
        "item_id": tail["item_id"].to_numpy(), "movement_bucket": tail["movement_bucket"].to_numpy(),
        "placement_class": tail["placement_class"].to_numpy(), "provisional": False,
        "primary_region": tail["primary_region"].to_numpy(), "footprint": tail["footprint"].to_numpy(),
        "primary_home": "STORAGE", "home_2": None, "home_3": None, "cost": np.nan, "has_policy": False})

    table = pd.concat([fwd_tbl, tail_tbl], ignore_index=True).sort_values("item_id").reset_index(drop=True)

    loads_rows = [{"building": names[b], "role": "forward", "cube_capacity": cap[b],
                   "cube_used": round(float(load[b]), 1), "utilization": round(float(load[b] / cap[b]), 3)}
                  for b in range(len(names))]
    stor_cap = float(state["locations"].set_index("building").loc["STORAGE", "cube_capacity"])
    stor_used = float(tail["footprint"].sum())
    loads_rows.append({"building": "STORAGE", "role": "storage", "cube_capacity": stor_cap,
                       "cube_used": round(stor_used, 1), "utilization": round(stor_used / stor_cap, 3)})
    loads = pd.DataFrame(loads_rows)

    return {"assign": assign, "cost_matrix": c, "table": table, "loads": loads,
            "total_cost": float(c[np.arange(n_items), assign].sum()),
            "overflow": overflow, "n_forward": n_items, "n_storage": int((~mask).sum()),
            "n_new": int((act["placement_class"] == "new").sum())}
