"""Movement classification, consumed from the demand engine rather than reinvented.

The demand engine classifies each item by its demand pattern using the Syntetos and
Boylan scheme: the average demand interval (ADI, how often it sells) and the squared
coefficient of variation of sale sizes (CV2, how variable those sales are) place it in
one of four quadrants, smooth, erratic, intermittent, or lumpy, with the standard cuts
at ADI 1.32 and CV2 0.49. It also draws a distinction this engine depends on: an item
that has never sold (no history at all) is new, not dead, even though both show zero
recent demand. Telling them apart is the whole point, because a brand-new item is
expected to move and a dead one is not.

This module maps that classification to a placement decision:

  active   real, ongoing demand           -> forward home, full policy
  new      never sold, no history yet      -> forward home, provisional cold-start policy
  slow     sells rarely and in low volume  -> storage, no policy
  dead     has history, no recent movement -> storage, no policy

Active and new items compete for forward cube. Slow and dead items are parked in
storage. The volume cuts that separate dead, slow, and active are adjustable per
operation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ADI_CUT = 1.32          # demand engine's Syntetos-Boylan cuts
CV2_CUT = 0.49
FORWARD_CLASSES = ("active", "new")
STORAGE_CLASSES = ("slow", "dead")


def sbc_bucket(adi, cv2):
    if not np.isfinite(adi) or not np.isfinite(cv2):
        return "new"
    if adi < ADI_CUT:
        return "smooth" if cv2 < CV2_CUT else "erratic"
    return "intermittent" if cv2 < CV2_CUT else "lumpy"


def classify_movement(items, dead_cut=0.1, slow_cut=2.0):
    """Return a frame with the demand-pattern bucket and the placement class."""
    buckets, placement = [], []
    for r in items.itertuples():
        never_sold = bool(getattr(r, "never_sold"))
        mean = getattr(r, "mean_demand")
        if never_sold:
            buckets.append("new"); placement.append("new"); continue
        bucket = sbc_bucket(getattr(r, "adi"), getattr(r, "cv2"))
        buckets.append(bucket)
        if not np.isfinite(mean) or mean <= dead_cut:
            placement.append("dead")                       # had history, no recent movement
        elif bucket in ("intermittent", "lumpy") and mean < slow_cut:
            placement.append("slow")                       # sells rarely, low volume
        else:
            placement.append("active")
    return pd.DataFrame({"movement_bucket": buckets, "placement_class": placement},
                        index=items.index)
