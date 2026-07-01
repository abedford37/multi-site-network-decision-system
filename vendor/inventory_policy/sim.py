"""Shared demand model: the ground-truth process behind each item.

Used two ways: to derive the forecast mean and standard deviation an item would
show (as the demand engine would estimate them), and to simulate realized service
in evaluation. Four patterns match the demand engine's SBC classification. The
point of keeping intermittent and lumpy demand genuinely spiky is that a normal
buffer under-covers them, which is exactly what the improved policy must fix.
"""
from __future__ import annotations

import numpy as np

PATTERNS = ["smooth", "erratic", "intermittent", "lumpy"]


def _params(pattern):
    return {"smooth": {"kind": "normal", "cv": 0.20},
            "erratic": {"kind": "normal", "cv": 0.60},
            "intermittent": {"kind": "occ", "p": 0.40},
            "lumpy": {"kind": "occ_var", "p": 0.30, "size_cv": 0.70}}[pattern]


def sample_daily(pattern, d, rng, n):
    pr = _params(pattern)
    if pr["kind"] == "normal":
        return np.clip(rng.normal(d, pr["cv"] * d, n), 0, None)
    if pr["kind"] == "occ":
        p = pr["p"]
        return rng.binomial(1, p, n) * (d / p)
    p, scv = pr["p"], pr["size_cv"]
    size_mean = d / p
    return np.clip(rng.binomial(1, p, n) * rng.normal(size_mean, scv * size_mean, n), 0, None)


def sample_ltd(pattern, d, lt_mean, lt_std, rng, n=4000):
    """Lead-time demand samples: random lead time, then demand summed over it."""
    L = np.clip(rng.normal(lt_mean, lt_std, n), 1, None)
    Li = np.round(L).astype(int)
    pr = _params(pattern)
    if pr["kind"] == "normal":
        sigma = pr["cv"] * d
        return np.clip(rng.normal(L * d, np.sqrt(L) * sigma), 0, None)
    if pr["kind"] == "occ":
        p = pr["p"]
        return rng.binomial(Li, p) * (d / p)
    p, scv = pr["p"], pr["size_cv"]
    size_mean = d / p
    occ = rng.binomial(Li, p)
    return np.clip(rng.normal(occ * size_mean, np.sqrt(np.maximum(occ, 1)) * scv * size_mean), 0, None)


def daily_stats(pattern, d, rng, n=20000):
    s = sample_daily(pattern, d, rng, n)
    return float(s.mean()), float(s.std())
