"""Cost matrix for the active items over the forward buildings only. Homing active
item i in forward building b costs its demand times the building's handling rate,
plus its demand times the expected ship distance from b to where the item's demand
is. Storage items are excluded: they have no demand and no forward home to cost.
"""
from __future__ import annotations

from .data import forward_view


def cost_matrix(state):
    _, act, ashares, fwd, dist = forward_view(state)
    exp_dist = ashares @ dist.T                                  # (active_items, forward_buildings)
    c = act["demand"].to_numpy()[:, None] * (fwd["handling"].to_numpy()[None, :] + exp_dist)
    return c
