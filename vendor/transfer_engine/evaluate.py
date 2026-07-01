"""Measure what the plan accomplishes, and prove the ladder beats tier-blind.

Applies the chosen transfers to a copy of on-hand and scores the result: how much
of today's confirmed outbound demand the shipping buildings can now serve, how many
below-MIN items were restored, how much visitor and excess stock was cleared, and
whether every forward building ends within capacity. The same is run for the
tier-blind baseline under the same capacity, so the outbound fill difference is the
value of prioritizing.
"""
from __future__ import annotations

import pandas as pd

from .candidates import build_candidates
from .optimize import schedule
from .nodes import FORWARD


def _apply(state, chosen):
    oh = dict(state["onhand"])
    for c in chosen.itertuples():
        oh[(c.item, c.from_loc)] = oh.get((c.item, c.from_loc), 0) - c.qty
        oh[(c.item, c.to_loc)] = oh.get((c.item, c.to_loc), 0) + c.qty
    return oh


def _metrics(state, chosen):
    items = state["items"]
    home = dict(zip(items.item_id, items.home))
    minq = dict(zip(items.item_id, items.min_qty))
    maxq = dict(zip(items.item_id, items.max_qty))
    ophq = dict(zip(items.item_id, items.ophq_qty))
    orders = state["orders"]
    oh0, oh1 = state["onhand"], _apply(state, chosen)

    ordered_units = sum(orders.values())
    pre = sum(min(oh0.get((it, home[it]), 0), q) for it, q in orders.items())
    covered = sum(min(oh1.get((it, home[it]), 0), q) for it, q in orders.items())
    gap = ordered_units - pre
    below0 = [it for it in items.item_id if oh0.get((it, home[it]), 0) < minq[it]]
    restored = sum(1 for it in below0 if oh1.get((it, home[it]), 0) >= minq[it])
    vis0 = sum(v for (i, l), v in oh0.items() if l in FORWARD and home[i] != l)
    vis1 = sum(v for (i, l), v in oh1.items() if l in FORWARD and home[i] != l)
    exc0 = sum(max(0, oh0.get((it, home[it]), 0) - maxq[it]) for it in items.item_id)
    exc1 = sum(max(0, oh1.get((it, home[it]), 0) - maxq[it]) for it in items.item_id)
    caps = dict(zip(state["locations"].location, state["locations"].capacity))
    fill1 = {f: sum(v for (i, l), v in oh1.items() if l == f) for f in FORWARD}
    return {"outbound_shortfall_closed": round((covered - pre) / gap, 3) if gap > 0 else 1.0,
            "outbound_fill_rate": round(covered / ordered_units, 3) if ordered_units else 0.0,
            "below_min_restored": f"{restored}/{len(below0)}",
            "visitor_units_cleared": round(vis0 - vis1, 0),
            "excess_units_relieved": round(exc0 - exc1, 0),
            "forward_within_capacity": all(fill1[f] <= caps[f] + 1e-6 for f in FORWARD)}


def compare(state):
    cands, suppressed = build_candidates(state)
    ladder = schedule(state, cands, "ladder")
    blind = schedule(state, cands, "blind")
    tbl = pd.DataFrame({"ladder (engine)": _metrics(state, ladder["chosen"]),
                        "tier-blind baseline": _metrics(state, blind["chosen"])}).T
    return tbl, ladder, suppressed
