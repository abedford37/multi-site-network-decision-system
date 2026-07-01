"""Convenience entry point: catalog in, policy table out."""
from __future__ import annotations

from .faithful import faithful_policy
from .improved import improved_policy


def plan(data, method="improved", **kw):
    items = data["items"]
    return improved_policy(items, **kw) if method == "improved" else faithful_policy(items)
