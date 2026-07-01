"""The unified MSDN state: every stage's output plus one master per-item record."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class MSDNState:
    catalog: dict
    forecast: pd.DataFrame
    classification: pd.DataFrame
    policy: pd.DataFrame
    home: dict
    container: dict
    transfer: dict
    master: pd.DataFrame

    def summary(self):
        t = self.home["table"]
        r = self.container["result"]
        req = r.required_total or 1.0
        covered = 1.0 - sum(r.remaining.values()) / req
        m = self.transfer["metrics"].loc["ladder (engine)"]
        return {
            "items": len(self.catalog["items"]),
            "buckets": self.classification["bucket"].value_counts().to_dict(),
            "abc": self.policy["abc"].value_counts().to_dict(),
            "placement": t["placement_class"].value_counts().to_dict(),
            "forward_homed": int(t["primary_home"].isin(["FWD-A", "FWD-B"]).sum()),
            "storage_homed": int((t["primary_home"] == "STORAGE").sum()),
            "containers_scheduled": len(r.assignments),
            "containers_deferred": len(r.deferred),
            "container_coverage": round(covered, 3),
            "transfers_used": self.transfer["result"]["used"],
            "outbound_shortfall_closed": m["outbound_shortfall_closed"],
            "suppressed_by_inbound": self.transfer["result"]["suppressed_by_inbound"],
        }
