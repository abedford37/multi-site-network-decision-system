"""Faithful reproduction of the KNIME MIN / OPHQ / MAX calculation.

Now transcribed from both source sheets, so the OHQ Service Level fields are the
real definitions rather than stand-ins. The Service Level sheet defines three
confidence levels of no stockout, each as mean lead-time demand times a z-value:

  OHQ Service Level 3 = Total Lead Time Days * daily demand * 0.84   (80% confidence)
  OHQ Service Level 4 = Total Lead Time Days * daily demand * 1.04   (85% confidence)
  OHQ Service Level 5 = Total Lead Time Days * daily demand * 1.28   (90% confidence)

and a weekly version of each as (OHQ Service Level k / Total Lead Time Days) * 7.
The MIN/MAX sheet then wires them up:

  MIN            = lead-time demand * 1.04   (equals OHQ Service Level 4)
  MAX            = lead-time demand * 1.28   (equals OHQ Service Level 5)
  Quantity Multiple = lead-time demand * 0.84 (equals OHQ Service Level 3)
  ABC Demand Value  = Weekly OHQ Service Level 3 = daily demand * 7 * 0.84
  OPHQ              = Weekly OHQ Service Level 4 = daily demand * 7 * 1.04

Two flaws are reproduced honestly. The z-values multiply mean lead-time demand
rather than the standard deviation of lead-time demand, so the buffer ignores
variability, and the document's own callout formula (sigma_LT * Z * D_Avg) is not
what the nodes compute. And OPHQ is one week of stock while MIN is a full lead time
of stock, so for any item with a lead time beyond 7 days OPHQ falls below MIN, which
the evaluation surfaces.
"""
from __future__ import annotations

import pandas as pd


def faithful_policy(items: pd.DataFrame) -> pd.DataFrame:
    dd = items["daily_mean"]                 # 7 Purchase Cycle Average per Day
    lt = items["lead_time_days"]             # Total Lead Time Days
    base = lt * dd                           # lead-time demand

    sl3, sl4, sl5 = base * 0.84, base * 1.04, base * 1.28   # 80 / 85 / 90 percent
    return pd.DataFrame({
        "item_id": items["item_id"],
        "min_qty": sl4.round(1),                     # lead-time demand * 1.04
        "ophq_qty": ((sl4 / lt) * 7).round(1),       # weekly version of the 85% level
        "max_qty": sl5.round(1),                     # lead-time demand * 1.28
        "qty_multiple": sl3.round(1),                # lead-time demand * 0.84
        "abc_demand_value": ((sl3 / lt) * 7).round(1),
        "method": "faithful",
    })
