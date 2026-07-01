"""Attribute-driven home-building assignment.

Generalized from a real Building Assignment by Item Designation workflow, which
routed each item to a building using size, parcel eligibility, weight, fragility,
demand velocity, and sales distribution. Here it is a transparent scoring match
between item attributes and building capability, so it extends to any number of
buildings. Home assignment is an INPUT to the optimizer, computed once here.
"""
from __future__ import annotations

import pandas as pd


def score(item, building) -> int:
    s = 0
    s += 1 if item["size"] == building.size_pref else 0
    s += 1 if bool(item["parcel"]) == bool(building.parcel) else 0
    return s


def assign_home(item, buildings) -> str:
    best, best_score = buildings[0].name, -1
    for b in buildings:
        sc = score(item, b)
        if sc > best_score:
            best, best_score = b.name, sc
    return best


def assign_homes(items: pd.DataFrame, buildings) -> pd.DataFrame:
    out = items.copy()
    out["home"] = out.apply(lambda r: assign_home(r, buildings), axis=1)
    return out
