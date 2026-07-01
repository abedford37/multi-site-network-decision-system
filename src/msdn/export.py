"""Publish the pipeline's decision as a neutral record a downstream product can consume.

The umbrella's job ends at a decision per item. A product layer on top, for example the
Operational Intelligence OS, needs that decision plus the operational positions to reason
about. This writes both as one JSON record in the pipeline's own vocabulary (home,
ophq_qty, cbm_per_unit). The consumer maps those terms into its own schema. Keeping the
record neutral is what keeps the two systems loosely coupled: neither has to know the
other's internal shape.
"""
from __future__ import annotations

import json


def build_decision_record(state):
    """Return the decision record as a plain dict: network, items, positions."""
    loads = state.home["loads"]
    daily_capacity = state.transfer["state"]["daily_capacity"]
    network = [{"building": r.building, "role": r.role,
                "cube_capacity": round(float(r.cube_capacity), 1),
                "transfer_capacity": int(daily_capacity)}
               for r in loads.itertuples()]

    fc = state.forecast.set_index("item_id")
    cat = state.catalog["items"].set_index("item_id")
    items = []
    for r in state.master.itertuples():
        it = r.item_id
        items.append({
            "item_id": it, "home": r.primary_home,
            "daily_mean": round(float(r.daily_mean), 3),
            "daily_std": round(float(fc.at[it, "daily_std"]), 3),
            "service_level": float(r.service_level) if r.service_level == r.service_level else None,
            "min_qty": None if r.min_qty != r.min_qty else round(float(r.min_qty), 1),
            "ophq_qty": None if r.ophq_qty != r.ophq_qty else round(float(r.ophq_qty), 1),
            "max_qty": None if r.max_qty != r.max_qty else round(float(r.max_qty), 1),
            "has_policy": bool(r.has_policy),
            "lead_time_days": float(cat.at[it, "lead_time_days"]),
            "lead_time_std": float(cat.at[it, "lead_time_std"]),
            "pack_size": int(cat.at[it, "pack_size"]),
            "cbm_per_unit": float(cat.at[it, "cbm_per_unit"]),
        })

    positions = [{"item_id": i, "location": loc, "onhand": round(float(v), 1)}
                 for (i, loc), v in state.transfer["state"]["onhand"].items()]

    return {"generated_by": "MSDN pipeline",
            "contract_version": "1.0",
            "network": network, "items": items, "positions": positions}


def export_decision_record(state, path):
    record = build_decision_record(state)
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return record
