"""Improved statistical policy: same backbone, correct buffer.

Keeps lead-time demand as the anchor and per-supplier lead time. Fixes the buffer
by making it a function of uncertainty, not a percent of the mean:

  mu_LTD    = lead_time_mean * daily_demand
  sigma_LTD = sqrt(lead_time_mean * demand_var + daily_demand^2 * lead_time_var)
  MIN (reorder point) = service-level quantile of lead-time demand

For smooth and erratic items the quantile is the normal one, mu_LTD + z * sigma_LTD.
For intermittent and lumpy items the normal curve under-covers the right tail, so
the reorder point is the quantile of a gamma distribution moment-matched to the
same mean and variance, which respects the skew (a standard treatment for spiky
demand). Service level is set per ABC class, so it is an explicit target.

Order quantity comes from a review-period cover, floored at MOQ and rounded up to
pack, which is where the 0.84 quantity multiple really belongs. OPHQ = MIN + Q and
MAX = OPHQ + Q, so MIN <= OPHQ <= MAX holds by construction.
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from .classify import sku_strategy


def improved_policy(items: pd.DataFrame, review_days=7, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = []
    for r in items.itertuples():
        d, sd, lt, lts = r.daily_mean, r.daily_std, r.lead_time_days, r.lead_time_std
        z = NormalDist().inv_cdf(r.service_level)
        mu = lt * d
        var = lt * sd ** 2 + d ** 2 * lts ** 2
        sigma = math.sqrt(max(var, 0.0))
        if r.pattern in ("smooth", "erratic") or var <= 0 or mu <= 0:
            reorder = mu + z * sigma
        else:
            shape, scale = mu ** 2 / var, var / mu           # gamma matched to (mu, var)
            reorder = float(np.quantile(rng.gamma(shape, scale, 6000), r.service_level))
        ss = max(0.0, reorder - mu)
        q = max(r.moq, math.ceil((review_days * d) / r.pack_size) * r.pack_size)
        ophq = reorder + q
        out.append({"item_id": r.item_id, "min_qty": round(reorder, 1),
                    "ophq_qty": round(ophq, 1), "max_qty": round(ophq + q, 1),
                    "safety_stock": round(ss, 1), "order_qty": q,
                    "sku_strategy": sku_strategy(r.abc, r.pattern), "method": "improved"})
    return pd.DataFrame(out)
