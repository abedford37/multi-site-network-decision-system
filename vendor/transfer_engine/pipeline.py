"""Convenience entry point: network state in, transfer plan out."""
from __future__ import annotations

from .candidates import build_candidates
from .optimize import schedule


def plan(state):
    candidates, suppressed = build_candidates(state)
    result = schedule(state, candidates, "ladder")
    result["suppressed_by_inbound"] = suppressed
    return result
