"""Run the five engines in dependency order on one shared catalog."""
from __future__ import annotations

import pandas as pd

from .catalog import generate as generate_catalog
from . import adapters as A
from .state import MSDNState


def _build_master(catalog, forecast, classification, policy, home, transfer):
    m = (catalog["items"][["item_id", "latent_pattern", "category", "origin", "lead_time_days"]]
         .merge(classification[["item_id", "bucket", "never_sold"]], on="item_id")
         .merge(forecast[["item_id", "daily_mean"]], on="item_id")
         .merge(policy[["item_id", "abc", "service_level", "min_qty", "ophq_qty", "max_qty"]],
                on="item_id", how="left")
         .merge(home["table"][["item_id", "placement_class", "primary_home", "home_2", "has_policy"]],
                on="item_id", how="left"))
    chosen = transfer["result"]["chosen"]
    if len(chosen):
        moved = (chosen.groupby("item")["tier"].min().rename("transfer_tier").reset_index()
                 .rename(columns={"item": "item_id"}))
        m = m.merge(moved, on="item_id", how="left")
    else:
        m["transfer_tier"] = pd.NA
    return m


def run_pipeline(catalog=None, seed=42):
    catalog = catalog or generate_catalog(seed=seed)
    forecast, classification = A.run_demand(catalog)
    policy = A.run_policy(catalog, forecast, classification)
    home = A.run_home(catalog, forecast, classification, policy)
    container = A.run_container(catalog, forecast, home["table"])
    transfer = A.run_transfer(catalog, policy, home["table"], container["inbound"])
    master = _build_master(catalog, forecast, classification, policy, home, transfer)
    return MSDNState(catalog, forecast, classification, policy, home, container, transfer, master)
