"""Probabilistic demand: cover the forecast at a service level, not a point.

The optimizer covers demand at a target service level. Given a per-item forecast
mean and standard deviation (supplied by the demand engine), the required coverage
is the service-level quantile of the demand distribution, so a higher service level
asks the network to carry more. This is what makes the recommendation probabilistic
rather than a fixed-number pull.
"""
from __future__ import annotations

from statistics import NormalDist

import pandas as pd


def required_coverage(mean, std, service_level=0.95):
    z = NormalDist().inv_cdf(service_level)
    return max(0.0, float(mean + z * std))


def required_table(demand: pd.DataFrame, service_level=0.95) -> dict:
    """demand: columns item_id, mean, std. Returns item_id -> required units."""
    return {r.item_id: required_coverage(r.mean, r.std, service_level)
            for r in demand.itertuples()}
