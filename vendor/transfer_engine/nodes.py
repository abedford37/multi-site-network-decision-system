"""Network locations by function. A reserve campus holds safety stock and excess,
and forward buildings ship to customers and have finite space. Stock of an item at
a forward building that is not its home is a visitor. Real site names live in
configuration; nothing here hardcodes a warehouse.
"""
from __future__ import annotations

import pandas as pd

STORAGE = "STORAGE"
FORWARD = ["FWD-A", "FWD-B"]


def default_locations(cap_a, cap_b, reserve_cap=10_000_000):
    return pd.DataFrame([
        {"location": STORAGE, "role": "reserve", "capacity": reserve_cap},
        {"location": "FWD-A", "role": "forward", "capacity": cap_a},
        {"location": "FWD-B", "role": "forward", "capacity": cap_b},
    ])
