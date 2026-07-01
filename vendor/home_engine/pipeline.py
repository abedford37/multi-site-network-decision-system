"""Convenience entry point: slotting instance in, home table out."""
from __future__ import annotations

from .assign import assign_items


def assign_homes(state):
    return assign_items(state)
