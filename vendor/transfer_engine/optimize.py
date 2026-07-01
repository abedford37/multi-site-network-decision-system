"""Select the day's transfers under the daily capacity, by the tier ladder.

Candidates are taken strictly in tier order, and within a tier by priority (overdue
and fast movers first). Each selected transfer consumes one unit of the daily
capacity and must have room at its destination, since forward buildings are finite.
Reserve is treated as effectively unbounded. What does not fit is deferred to a
later day. Unsourceable needs are set aside as purchasing gaps, not scheduled.

The ladder strategy is the engine. The tier-blind strategy is a baseline that uses
the same capacity but ignores priority, included so the value of prioritizing is
measured rather than asserted.
"""
from __future__ import annotations

import pandas as pd

from .candidates import NO_SOURCE


def schedule(state, candidates, strategy="ladder"):
    caps = dict(zip(state["locations"].location, state["locations"].capacity))
    fill = {f: sum(v for (i, l), v in state["onhand"].items() if l == f)
            for f in caps}

    valid = candidates[candidates["from_loc"] != NO_SOURCE].copy()
    unsourceable = candidates[candidates["from_loc"] == NO_SOURCE].copy()

    if strategy == "ladder":
        valid = valid.sort_values(["tier", "priority"], ascending=[True, False])
    else:
        valid = valid.sample(frac=1.0, random_state=1)     # tier-blind baseline

    chosen, deferred, used = [], [], 0
    for c in valid.itertuples():
        if used >= state["daily_capacity"]:
            deferred.append(c._asdict())
            continue
        if fill.get(c.to_loc, 0) + c.qty > caps.get(c.to_loc, float("inf")) + 1e-6:
            deferred.append(c._asdict())
            continue
        fill[c.to_loc] = fill.get(c.to_loc, 0) + c.qty
        fill[c.from_loc] = fill.get(c.from_loc, 0) - c.qty
        chosen.append(c._asdict())
        used += 1

    keep = ["item", "from_loc", "to_loc", "qty", "tier", "reason"]
    to_df = lambda rows: (pd.DataFrame(rows)[keep] if rows else pd.DataFrame(columns=keep))
    return {"chosen": to_df(chosen), "deferred": to_df(deferred),
            "unsourceable": unsourceable[keep] if len(unsourceable) else pd.DataFrame(columns=keep),
            "fill": fill, "used": used}
