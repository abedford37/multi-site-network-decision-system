"""Synthetic network state for one planning day.

Items carry a home building and an adopted MIN / OPHQ / MAX policy (the output of
the inventory policy engine). On-hand is spread across home, reserve, and visitor
locations. There are confirmed outbound orders for today, near-term demand, inbound
containers arriving over the next few days (the container engine's ETAs), and a
daily transfer capacity that binds. Forward capacity is set so one building starts
over its limit, which exercises capacity relief. Reproducible via seed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .nodes import FORWARD, STORAGE, default_locations


def generate(n_items=140, seed=42, daily_capacity=60, inbound_window=3):
    rng = np.random.default_rng(seed)
    rows, onhand = [], {}
    orders, overdue, nearterm, inbound = {}, set(), {}, []

    for i in range(1, n_items + 1):
        it = f"IT-{i:04d}"
        home = FORWARD[int(rng.integers(0, len(FORWARD)))]
        min_q = float(rng.uniform(20, 200))
        q = float(rng.uniform(0.25, 0.5) * min_q)
        ophq, max_q = min_q + q, min_q + 2 * q
        abc = rng.choice(["A", "B", "C"], p=[0.2, 0.3, 0.5])
        velocity = {"A": rng.uniform(3, 5), "B": rng.uniform(1.5, 3), "C": rng.uniform(0.2, 1.5)}[abc]
        rows.append({"item_id": it, "home": home, "min_qty": round(min_q, 1),
                     "ophq_qty": round(ophq, 1), "max_qty": round(max_q, 1),
                     "abc": abc, "velocity": round(float(velocity), 2)})

        # home on-hand: below min / in band / above max
        state = rng.choice(["below", "band", "above"], p=[0.4, 0.4, 0.2])
        if state == "below":
            oh = rng.uniform(0.2, 0.9) * min_q
        elif state == "band":
            oh = rng.uniform(min_q, ophq)
        else:
            oh = rng.uniform(max_q, 1.4 * max_q)
        onhand[(it, home)] = round(float(oh), 1)

        # reserve stock available to source (a minority have none: network shortage)
        onhand[(it, STORAGE)] = round(float(rng.uniform(0.5, 1.5) * ophq)
                                      if rng.random() < 0.88 else 0.0, 1)

        # visitor stock at the other forward building for ~18% of items
        if rng.random() < 0.18:
            other = [f for f in FORWARD if f != home][0]
            onhand[(it, other)] = round(float(rng.uniform(0.2, 1.0) * ophq), 1)

        # confirmed outbound today (~45% of items), a few overdue
        if rng.random() < 0.45:
            orders[it] = round(float(rng.uniform(0.3, 1.2) * ophq), 1)
            if rng.random() < 0.12:
                overdue.add(it)
        # near-term demand (~50%)
        if rng.random() < 0.5:
            nearterm[it] = round(float(rng.uniform(0.1, 0.6) * ophq), 1)
        # inbound container arriving soon (~15%)
        if rng.random() < 0.15:
            inbound.append({"item": it, "to_loc": home,
                            "qty": round(float(rng.uniform(0.5, 1.5) * ophq), 1),
                            "eta": int(rng.integers(1, inbound_window + 2))})

    items = pd.DataFrame(rows)
    # forward capacity: FWD-A deliberately tight (starts over), FWD-B comfortable
    fill = {f: sum(v for (i, l), v in onhand.items() if l == f) for f in FORWARD}
    locations = default_locations(cap_a=round(fill["FWD-A"] * 0.92, 1),
                                  cap_b=round(fill["FWD-B"] * 1.15, 1))
    return {"items": items, "onhand": onhand, "orders": orders, "overdue": overdue,
            "nearterm": nearterm, "inbound": inbound, "locations": locations,
            "forward_locs": FORWARD, "daily_capacity": daily_capacity,
            "inbound_window": inbound_window}
