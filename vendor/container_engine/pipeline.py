"""Convenience entry point: turn a forecast and containers into a plan.

Homes and the demand forecast are inputs, computed upstream (the attribute rules
and the demand engine). This engine consumes them and never recomputes them,
which keeps the pipeline a straight line with no cycles.
"""
from __future__ import annotations

from .demand import required_table
from .optimize import schedule


def plan(data, service_level=0.95, strategy="greedy"):
    required = required_table(data["demand"], service_level)
    result = schedule(data, required, strategy)
    return result, required
