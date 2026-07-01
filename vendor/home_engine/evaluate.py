"""Bracket the active-item assignment between the unconstrained floor and a feasible
baseline, and report the storage tail separately. The floor puts every active item in
its cheapest forward building ignoring capacity: least cost possible, but it overloads
buildings, so it is infeasible. The balanced baseline is cost-blind, placing each item
where there is the most room: feasible but geography-blind. A good engine sits just
above the floor while feasible, and well below the baseline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .assign import assign_items
from .cost import cost_matrix
from .data import forward_view


def compare(state):
    mask, act, ashares, fwd, dist = forward_view(state)
    c = cost_matrix(state)
    fp = act["footprint"].to_numpy()
    cap = fwd["cube_capacity"].to_numpy().astype(float)
    n = c.shape[0]

    lb_assign = c.argmin(axis=1)
    lb_cost = float(c[np.arange(n), lb_assign].sum())
    lb_load = np.array([fp[lb_assign == b].sum() for b in range(len(cap))])
    lb_feasible = bool((lb_load <= cap + 1e-6).all())

    remaining = cap.copy()
    bal = np.full(n, -1)
    for i in np.argsort(-fp):
        b = int(np.argmax(remaining)); bal[i] = b; remaining[b] -= fp[i]
    bal_cost = float(c[np.arange(n), bal].sum())

    eng = assign_items(state)
    first_choice = float((eng["assign"] == lb_assign).mean())

    tbl = pd.DataFrame({
        "total_cost": {"unconstrained floor": round(lb_cost, 0), "engine": round(eng["total_cost"], 0),
                       "balanced baseline": round(bal_cost, 0)},
        "gap_to_floor": {"unconstrained floor": "0.0%", "engine": f"{(eng['total_cost']/lb_cost-1):.1%}",
                         "balanced baseline": f"{(bal_cost/lb_cost-1):.1%}"},
        "feasible": {"unconstrained floor": lb_feasible, "engine": True, "balanced baseline": True}})
    return tbl, eng, first_choice
