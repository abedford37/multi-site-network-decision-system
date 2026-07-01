"""Generate candidate transfers for the day, one list across all six tiers.

Tier ladder, highest first:
  0 capacity relief   move stock out of a forward building that is over its limit,
                      or will be once imminent inbound lands, so receiving is not blocked
  1 outbound today    bring stock to the shipping building to cover confirmed orders,
                      overdue first
  2 near-term demand  pre-position for demand in the next few days
  3 forward replenish raise home stock toward OPHQ when it is below MIN, fast movers first
  4 visitor return    move misplaced stock home, or to reserve if home is full
  5 excess relief     move stock above MAX back to reserve, down to OPHQ

Two cross-cutting rules are applied here, not as separate tiers. Inbound awareness
suppresses a forward need (tiers 1 to 3) that an imminent container will cover, so
the engine does not move stock the dock is about to deliver. And smart sourcing
fills a forward need from a visitor location first when one holds the item, so a
single move covers the shortage and clears the visitor at once; reserve is the
fallback. When neither can source a need it is flagged unsourceable, a purchasing
gap a transfer cannot fix.
"""
from __future__ import annotations

import pandas as pd

from .nodes import FORWARD, STORAGE

NO_SOURCE = "__NONE__"


def _prio(item, tier, overdue, vel, abc):
    p = vel.get(item, 1.0) + {"A": 100, "B": 50, "C": 10}[abc.get(item, "C")]
    if tier == 1 and item in overdue:
        p += 1000
    return p


def build_candidates(state):
    items = state["items"]
    oh = dict(state["onhand"])
    home = dict(zip(items.item_id, items.home))
    minq = dict(zip(items.item_id, items.min_qty))
    ophq = dict(zip(items.item_id, items.ophq_qty))
    maxq = dict(zip(items.item_id, items.max_qty))
    vel = dict(zip(items.item_id, items.velocity))
    abc = dict(zip(items.item_id, items.abc))
    orders, overdue, nearterm = state["orders"], state["overdue"], state["nearterm"]
    window = state["inbound_window"]

    inbound_cover, inbound_to = {}, {}
    for ib in state["inbound"]:
        if ib["eta"] <= window:
            if ib["to_loc"] == home.get(ib["item"]):
                inbound_cover[ib["item"]] = inbound_cover.get(ib["item"], 0) + ib["qty"]
            inbound_to[ib["to_loc"]] = inbound_to.get(ib["to_loc"], 0) + ib["qty"]

    cands, suppressed = [], 0.0

    # Tier 0: capacity relief on forward buildings (current fill plus imminent inbound).
    fills = {f: sum(v for (i, l), v in oh.items() if l == f) for f in FORWARD}
    for f in FORWARD:
        cap = float(state["locations"].set_index("location").loc[f, "capacity"])
        overflow = fills[f] + inbound_to.get(f, 0) - cap
        if overflow <= 0:
            continue
        here = [(i, l) for (i, l) in oh.keys() if l == f and oh[(i, l)] > 0]
        # evict least critical first: home excess above MAX, then visitors, then low velocity
        def evict_key(k):
            i, l = k
            excess = oh[k] - maxq[i] if home[i] == f else 0
            is_visitor = home[i] != f
            has_order = i in orders
            return (-(excess > 0), -is_visitor, has_order, vel.get(i, 1.0))
        for i, l in sorted(here, key=evict_key):
            if overflow <= 0:
                break
            mv = round(min(overflow, oh[(i, l)]), 1)
            if mv <= 0:
                continue
            cands.append({"item": i, "from_loc": f, "to_loc": STORAGE, "qty": mv,
                          "tier": 0, "priority": 1e6, "reason": "capacity_relief"})
            overflow -= mv

    # Tiers 1 to 5, per item.
    for it in items.item_id:
        h = home[it]
        base = oh.get((it, h), 0.0)
        vis = {l: oh.get((it, l), 0.0) for l in FORWARD if l != h and oh.get((it, l), 0.0) > 0}
        reserve = oh.get((it, STORAGE), 0.0)

        o, nt = orders.get(it, 0.0), nearterm.get(it, 0.0)
        t1 = max(0.0, o - base)
        t2 = max(0.0, o + nt - base) - t1
        # forward replenishment triggers only when on-hand is below MIN, then targets OPHQ
        t3 = max(0.0, (ophq[it] - base) - t1 - t2) if base < minq[it] else 0.0

        cover = inbound_cover.get(it, 0.0)          # inbound-aware suppression
        reduced = []
        for q in (t1, t2, t3):
            r = min(q, cover)
            cover -= r
            suppressed += r
            reduced.append(q - r)
        t1, t2, t3 = reduced

        for tier, need, reason in [(1, t1, "outbound_today"), (2, t2, "near_term"),
                                   (3, t3, "forward_replen")]:
            rem = round(need, 1)
            if rem <= 0:
                continue
            for loc, avail in sorted(vis.items(), key=lambda kv: -kv[1]):   # visitor first
                if rem <= 0 or avail <= 0:
                    continue
                mv = round(min(rem, avail), 1)
                cands.append({"item": it, "from_loc": loc, "to_loc": h, "qty": mv,
                              "tier": tier, "priority": _prio(it, tier, overdue, vel, abc),
                              "reason": reason + "_from_visitor"})
                vis[loc] -= mv
                rem -= mv
            if rem > 0 and reserve > 0:
                mv = round(min(rem, reserve), 1)
                cands.append({"item": it, "from_loc": STORAGE, "to_loc": h, "qty": mv,
                              "tier": tier, "priority": _prio(it, tier, overdue, vel, abc),
                              "reason": reason})
                reserve -= mv
                rem -= mv
            if rem > 0.1:
                cands.append({"item": it, "from_loc": NO_SOURCE, "to_loc": h, "qty": round(rem, 1),
                              "tier": tier, "priority": _prio(it, tier, overdue, vel, abc),
                              "reason": reason + "_unsourceable"})

        # Tier 4: return remaining visitor stock home up to MAX, overflow to reserve.
        room = max(0.0, maxq[it] - base)
        for loc, avail in vis.items():
            if avail <= 0:
                continue
            to_home = round(min(avail, room), 1)
            if to_home > 0:
                cands.append({"item": it, "from_loc": loc, "to_loc": h, "qty": to_home,
                              "tier": 4, "priority": _prio(it, 4, overdue, vel, abc),
                              "reason": "visitor_repatriation"})
                room -= to_home
            rest = round(avail - to_home, 1)
            if rest > 0:
                cands.append({"item": it, "from_loc": loc, "to_loc": STORAGE, "qty": rest,
                              "tier": 4, "priority": _prio(it, 4, overdue, vel, abc),
                              "reason": "visitor_to_reserve"})

        # Tier 5: excess above MAX back to reserve, down to OPHQ.
        if base > maxq[it]:
            cands.append({"item": it, "from_loc": h, "to_loc": STORAGE,
                          "qty": round(base - ophq[it], 1), "tier": 5,
                          "priority": _prio(it, 5, overdue, vel, abc), "reason": "excess_relief"})

    return pd.DataFrame(cands), round(suppressed, 1)
