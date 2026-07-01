"""Demand classification.

Two-stage routing decision:

1. Data-sufficiency gate. An item without enough observed history cannot be
   classified or forecast on its own. It is routed to the cold-start path and
   borrows from its analog group.

2. SBC demand-pattern quadrant. Items with enough history are classified by two
   statistics computed from sales history alone, so the scheme works for any
   company regardless of its internal merchandising labels:
     ADI  = average demand interval = periods / number of demand events
     CV2  = squared coefficient of variation of the nonzero demand sizes
   The cut points 1.32 (ADI) and 0.49 (CV2) are from Syntetos, Boylan and Croston
   (2005), who derived them as the boundaries where one forecasting method
   overtakes another in expected error.

Missing periods (NaN) and true zero-demand periods (0) are kept distinct. A NaN
means we never observed the item that week; a 0 means we observed no demand.
Conflating them is a classic demand-forecasting error.
"""
from __future__ import annotations

import numpy as np

ADI_CUT = 1.32
CV2_CUT = 0.49

SMOOTH = "smooth"
ERRATIC = "erratic"
INTERMITTENT = "intermittent"
LUMPY = "lumpy"
NEW = "new"


def _observed(series):
    arr = np.asarray(series, dtype=float)
    return arr[~np.isnan(arr)]


def adi(series) -> float:
    """Average demand interval over observed periods."""
    obs = _observed(series)
    events = np.count_nonzero(obs)
    if events == 0:
        return np.inf
    return len(obs) / events


def cv2(series) -> float:
    """Squared coefficient of variation of the nonzero demand sizes."""
    obs = _observed(series)
    nz = obs[obs > 0]
    if len(nz) < 2 or nz.mean() == 0:
        return 0.0
    return float((nz.std(ddof=0) / nz.mean()) ** 2)


def has_sufficient_history(series, min_observed=8, min_events=3) -> bool:
    """Enough observed weeks and enough demand events to stand on its own."""
    obs = _observed(series)
    return len(obs) >= min_observed and np.count_nonzero(obs) >= min_events


def classify_item(series, min_observed=8, min_events=3) -> str:
    """Return one of: new, smooth, erratic, intermittent, lumpy."""
    if not has_sufficient_history(series, min_observed, min_events):
        return NEW
    a, c = adi(series), cv2(series)
    if a < ADI_CUT:
        return SMOOTH if c < CV2_CUT else ERRATIC
    return INTERMITTENT if c < CV2_CUT else LUMPY


# Which engine each bucket is routed to. Documented and asserted in tests.
ROUTING = {
    NEW: "group_cold_start",
    SMOOTH: "global_ml",
    ERRATIC: "global_ml",
    INTERMITTENT: "sba",
    LUMPY: "sba",
}
