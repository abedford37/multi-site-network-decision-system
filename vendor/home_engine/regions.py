"""Demand regions: the channels or metros that generate orders. Each sits somewhere
on the same plane as the buildings. The ship cost from a building to a region is the
distance between them times a per unit rate, so homing an item near its demand is
cheaper. Distances are Euclidean here; a real deployment would swap in lane rates.
"""
from __future__ import annotations

import numpy as np


def distance_matrix(buildings, regions, ship_rate=0.04):
    b = buildings[["x", "y"]].to_numpy()
    r = regions[["x", "y"]].to_numpy()
    d = np.sqrt(((b[:, None, :] - r[None, :, :]) ** 2).sum(axis=2))
    return d * ship_rate     # shape (n_buildings, n_regions)
