"""Adapters: project the shared catalog and accumulated outputs into each engine's
real input shape, call the real engine, and return its output. Nothing here
reimplements an engine; every adapter runs the vendored code on shared data.

The pipeline order is fixed by dependency: demand, then policy and the movement
gate, then home assignment, then container routing, then transfer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import _engines  # noqa: F401  (puts vendored engines on the path)
from demand_engine import DemandForecaster, classify_item, adi, cv2
from inventory_policy import improved_policy, abc_classify
from home_engine import assign_items, classify_movement
from container_engine import plan as container_plan
from container_engine.nodes import DEFAULT_FORWARD
from transfer_engine import build_candidates, compare as transfer_compare
from transfer_engine import schedule as transfer_schedule
from transfer_engine.nodes import default_locations, FORWARD, STORAGE


# ------------------------------------------------------------------ demand
def run_demand(catalog):
    demand, items = catalog["demand"], catalog["items"]
    meta = items[["item_id", "group", "category", "price"]].copy()
    forecaster = DemandForecaster().fit(demand, meta)
    week = int(demand["week_index"].max())
    pred = forecaster.predict_week(demand, meta, week)          # one-step forward forecast

    cls_rows = []
    for it, s in demand.groupby("item_id"):
        series = s.sort_values("week_index")["demand"].to_numpy(dtype=float)
        obs = series[~np.isnan(series)]
        try:
            a = float(adi(series)) if obs.size else np.nan
            c = float(cv2(series)) if obs.size else np.nan
        except Exception:
            a, c = np.nan, np.nan
        cls_rows.append({"item_id": it, "bucket": classify_item(series),
                         "adi": a, "cv2": c, "never_sold": bool(np.isnan(series).all())})
    classification = pd.DataFrame(cls_rows)

    fc = pred.groupby("item_id")["y_pred"].mean().rename("weekly_forecast").reset_index()
    recent = demand[demand["week_index"] > week - 8]
    stats = recent.groupby("item_id")["demand"].agg(weekly_mean="mean", weekly_std="std").reset_index()
    fc = fc.merge(stats, on="item_id", how="left")
    fc["weekly_mean"] = fc["weekly_mean"].fillna(0.0)
    fc["weekly_std"] = fc["weekly_std"].fillna(0.0)
    fc["weekly_forecast"] = fc["weekly_forecast"].fillna(fc["weekly_mean"]).clip(lower=0)
    fc["daily_mean"] = (fc["weekly_forecast"] / 7).clip(lower=0)
    fc["daily_std"] = (fc["weekly_std"] / np.sqrt(7)).fillna(0.0)
    return fc, classification


# ------------------------------------------------------------------ policy
def run_policy(catalog, forecast, classification):
    items = catalog["items"]
    df = (items[["item_id", "pack_size", "moq", "lead_time_days", "lead_time_std"]]
          .merge(forecast, on="item_id")
          .merge(classification[["item_id", "bucket"]], on="item_id"))
    df["pattern"] = df["bucket"].replace({"new": "smooth"})     # provisional pattern for cold-start items
    df = abc_classify(df)                                       # adds abc, service_level from weekly_mean
    policy = improved_policy(df)
    policy = policy.merge(df[["item_id", "abc", "service_level", "pattern"]], on="item_id")
    return policy


# ------------------------------------------------------------------ home
def run_home(catalog, forecast, classification, policy, seed=7):
    rng = np.random.default_rng(seed)
    items = catalog["items"]
    hi = (items[["item_id", "cbm_per_unit", "primary_region"]]
          .merge(forecast[["item_id", "daily_mean", "weekly_mean"]], on="item_id")
          .merge(classification[["item_id", "never_sold", "adi", "cv2"]], on="item_id")
          .merge(policy[["item_id", "ophq_qty"]], on="item_id"))
    hi = hi.rename(columns={"cbm_per_unit": "cube", "daily_mean": "demand"})
    # cost and footprint use the forecast; the dead/slow gate uses recent observed demand,
    # so an item that stopped selling reads as dead even if the forecaster still smooths it up
    hi["mean_demand"] = hi["weekly_mean"] / 7.0
    cls = classify_movement(hi)                                # SBC buckets + placement, same cuts as demand engine
    hi = pd.concat([hi, cls], axis=1)
    hi["provisional"] = hi["placement_class"] == "new"

    fwd_mask = hi["placement_class"].isin(["active", "new"]).to_numpy()
    leftover = rng.uniform(5, 120, len(hi)) * hi["cube"].to_numpy()
    hi["footprint"] = np.where(fwd_mask, hi["ophq_qty"].fillna(0) * hi["cube"],
                               np.round(leftover, 2))
    hi["ophq"] = np.where(fwd_mask, hi["ophq_qty"], np.nan)

    net = catalog["network"]
    locations = net[["building", "role", "x", "y", "handling"]].copy()
    locations["cube_capacity"] = np.nan
    fwd_fp = hi.loc[fwd_mask, "footprint"].sum()
    tail_fp = hi.loc[~fwd_mask, "footprint"].sum()
    locations.loc[locations.role == "forward", "cube_capacity"] = np.round(
        (fwd_fp / 0.85) * np.array([0.55, 0.45]), 1)
    locations.loc[locations.role == "storage", "cube_capacity"] = round(tail_fp / 0.85, 1)

    state = {"items": hi.reset_index(drop=True), "locations": locations,
             "regions": catalog["regions"], "shares": catalog["shares"]}
    result = assign_items(state)
    return result


# ------------------------------------------------------------------ container
def _build_containers(items_fwd, homes, n_containers, horizon, seed):
    rng = np.random.default_rng(seed)
    by_home = {b: homes.loc[homes.primary_home == b, "item_id"].tolist() for b in FORWARD}
    cpu = dict(zip(items_fwd.item_id, items_fwd.cbm_per_unit))
    cont_rows, content_rows = [], []
    for c in range(1, n_containers + 1):
        cid = f"CN-{c:04d}"
        target = rng.choice(FORWARD)
        others = [n for n in FORWARD if n != target]
        cbm, picked = 0.0, set()
        for _ in range(int(rng.integers(5, 11))):
            src = target if rng.random() < 0.8 else rng.choice(others)
            pool = by_home[src]
            if not pool:
                continue
            item = rng.choice(pool)
            if item in picked:
                continue
            picked.add(item)
            qty = int(rng.integers(10, 60))
            cbm += qty * cpu.get(item, 0.05)
            content_rows.append({"container_id": cid, "item_id": item, "qty": qty})
        eta = int(rng.integers(0, horizon))
        cont_rows.append({"container_id": cid, "eta_day": eta, "cbm": round(cbm, 2),
                          "free_until": eta + 3, "deadline": eta + 9,
                          "demurrage_per_day": round(float(rng.uniform(40, 150)), 2)})
    return pd.DataFrame(cont_rows), pd.DataFrame(content_rows)


def run_container(catalog, forecast, home_table, seed=42, n_containers=40, horizon=14, capacity=3):
    items = catalog["items"]
    homes = home_table[home_table.primary_home.isin(FORWARD)][["item_id", "primary_home"]]
    ci = (items[items.item_id.isin(homes.item_id)][["item_id", "size", "parcel", "weight", "cbm_per_unit"]]
          .merge(homes, on="item_id").rename(columns={"primary_home": "home"})
          .merge(forecast[["item_id", "daily_mean"]], on="item_id"))
    ci["velocity"] = ci["daily_mean"].round(2)
    demand = (forecast[forecast.item_id.isin(ci.item_id)][["item_id", "weekly_forecast", "weekly_std"]]
              .rename(columns={"weekly_forecast": "mean", "weekly_std": "std"}))
    containers, contents = _build_containers(ci, homes, n_containers, horizon, seed)

    data = {"buildings": DEFAULT_FORWARD, "items": ci, "demand": demand,
            "containers": containers, "contents": contents,
            "capacity": capacity, "horizon": horizon}
    result, required = container_plan(data)

    # inbound events for the transfer stage: scheduled container to building on day
    cmap = {cid: dict(zip(g.item_id, g.qty)) for cid, g in contents.groupby("container_id")}
    inbound = []
    for a in result.assignments:
        for item, qty in cmap.get(a["container"], {}).items():
            inbound.append({"item": item, "to_loc": a["building"], "qty": float(qty), "eta": int(a["day"])})
    return {"result": result, "required": required, "data": data, "inbound": inbound}


# ------------------------------------------------------------------ transfer
def run_transfer(catalog, policy, home_table, container_inbound, seed=11,
                 daily_capacity=40, inbound_window=3):
    rng = np.random.default_rng(seed)
    homes = home_table[home_table.primary_home.isin(FORWARD)][["item_id", "primary_home"]]
    pol = policy[policy.item_id.isin(homes.item_id)].merge(homes, on="item_id")

    rows, onhand = [], {}
    orders, overdue, nearterm = {}, set(), {}
    for r in pol.itertuples():
        it, home = r.item_id, r.primary_home
        mn, oq, mx = r.min_qty, r.ophq_qty, r.max_qty
        vel = float(rng.uniform(0.2, 5.0))
        rows.append({"item_id": it, "home": home, "min_qty": mn, "ophq_qty": oq,
                     "max_qty": mx, "abc": r.abc, "velocity": round(vel, 2)})
        state = rng.choice(["below", "band", "above"], p=[0.4, 0.4, 0.2])
        oh = (rng.uniform(0.2, 0.9) * mn if state == "below"
              else rng.uniform(mn, oq) if state == "band" else rng.uniform(mx, 1.4 * mx))
        onhand[(it, home)] = round(float(oh), 1)
        onhand[(it, STORAGE)] = round(float(rng.uniform(0.5, 1.5) * oq) if rng.random() < 0.88 else 0.0, 1)
        if rng.random() < 0.18:
            other = [f for f in FORWARD if f != home][0]
            onhand[(it, other)] = round(float(rng.uniform(0.2, 1.0) * oq), 1)
        if rng.random() < 0.45:
            orders[it] = round(float(rng.uniform(0.3, 1.2) * oq), 1)
            if rng.random() < 0.12:
                overdue.add(it)
        if rng.random() < 0.5:
            nearterm[it] = round(float(rng.uniform(0.1, 0.6) * oq), 1)

    items = pd.DataFrame(rows)
    fwd_items = set(items.item_id)
    inbound = [e for e in container_inbound if e["item"] in fwd_items and e["eta"] <= inbound_window]

    fill = {f: sum(v for (i, l), v in onhand.items() if l == f) for f in FORWARD}
    locations = default_locations(cap_a=round(fill["FWD-A"] * 0.92, 1),
                                  cap_b=round(fill["FWD-B"] * 1.15, 1))
    state = {"items": items, "onhand": onhand, "orders": orders, "overdue": overdue,
             "nearterm": nearterm, "inbound": inbound, "locations": locations,
             "forward_locs": list(FORWARD), "daily_capacity": daily_capacity,
             "inbound_window": inbound_window}
    metrics, ladder, suppressed = transfer_compare(state)
    ladder["suppressed_by_inbound"] = suppressed
    return {"result": ladder, "metrics": metrics, "state": state}
