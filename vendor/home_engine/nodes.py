"""Network locations. Four forward buildings can ship to customers and compete to
own active items; each has a location on the campus plane, a cube capacity, and a
handling rate (its internal cost per unit picked). One storage building holds dead
and slow inventory: items with little or no demand that carry no policy and should
not consume scarce forward space. Storage does not compete in the cost optimization;
it is the fixed home for the non-moving tail. Real site names live in configuration.
"""
from __future__ import annotations

import pandas as pd


def default_locations():
    # forward buildings compete for active items; storage is the fixed home for the tail
    return pd.DataFrame([
        {"building": "BLD-1", "role": "forward", "x": 20.0, "y": 25.0, "handling": 1.00, "cube_capacity": None},
        {"building": "BLD-2", "role": "forward", "x": 75.0, "y": 20.0, "handling": 1.15, "cube_capacity": None},
        {"building": "BLD-3", "role": "forward", "x": 30.0, "y": 78.0, "handling": 0.95, "cube_capacity": None},
        {"building": "BLD-4", "role": "forward", "x": 80.0, "y": 75.0, "handling": 1.05, "cube_capacity": None},
        {"building": "STORAGE", "role": "storage", "x": 50.0, "y": 50.0, "handling": 1.60, "cube_capacity": None},
    ])
