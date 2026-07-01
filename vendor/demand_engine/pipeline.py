"""The routing pipeline that ties classification, features, and methods together.

fit() classifies every item from its history, then trains one global gradient
boosted model per machine-learning bucket (smooth, erratic) rather than one model
across both. Pooling dissimilar patterns lets the heavy tail of erratic demand
bias the smooth forecasts upward, so we pool within a pattern, not across. SBA
serves the intermittent and lumpy buckets, and a shrinkage cold start serves new
items by blending their own early sales toward an analog group prior.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import classify as C
from .features import make_supervised, LAGS, ROLL
from .models import GlobalML, sba

ML_BUCKETS = (C.SMOOTH, C.ERRATIC)
SBA_BUCKETS = {C.INTERMITTENT, C.LUMPY}


class DemandForecaster:
    def __init__(self, min_observed=8, min_events=3, random_state=42):
        self.min_observed = min_observed
        self.min_events = min_events
        self.random_state = random_state

    def classify(self, demand):
        return {item: C.classify_item(s["demand"].values, self.min_observed, self.min_events)
                for item, s in demand.groupby("item_id")}

    def _items_in(self, bucket):
        return [i for i, b in self.buckets.items() if b == bucket]

    def fit(self, demand, items):
        self.items = items
        self.buckets = self.classify(demand)
        self.max_week = int(demand["week_index"].max())
        self.week_dates = demand.groupby("week_index")["date"].first().to_dict()
        weeks = sorted(demand["week_index"].unique())[max(LAGS):]

        self.ml_models, self.feat_cols = {}, None
        for b in ML_BUCKETS:
            its = self._items_in(b)
            if not its:
                continue
            rows, feat = make_supervised(demand[demand["item_id"].isin(its)], items, weeks)
            self.feat_cols = feat
            if len(rows) > 50:
                self.ml_models[b] = GlobalML(self.random_state).fit(rows[feat], rows["demand"])

        d = demand.merge(items[["item_id", "group"]], on="item_id")
        # Analog prior for cold start uses the group's regular items, since a new
        # SKU usually grows into a regular one; averaging in intermittent zeros
        # would bias the prior low.
        regular_items = [i for i, b in self.buckets.items() if b in ML_BUCKETS]
        dr = d[d["item_id"].isin(regular_items)]
        recent = dr[dr["week_index"] > self.max_week - ROLL]
        self.group_recent = recent.groupby("group")["demand"].mean().to_dict()
        self.global_recent = float(recent["demand"].mean()) if len(recent) else \
            float(d[d["week_index"] > self.max_week - ROLL]["demand"].mean())
        return self

    def predict_week(self, demand, items, week):
        """One-step forecast for `week`, using only history before `week`."""
        hist = demand[demand["week_index"] < week]
        date = self.week_dates.get(week)
        preds, seen = [], set()

        for b, model in self.ml_models.items():
            its = self._items_in(b)
            frame = pd.concat([hist, _placeholder(items, its, week, date)], ignore_index=True)
            rows, _ = make_supervised(frame, items, [week])
            if len(rows):
                yhat = model.predict(rows[self.feat_cols])
                for item, yp in zip(rows["item_id"], yhat):
                    preds.append((item, b, "global_ml", float(yp)))
                    seen.add(item)

        for item, b in self.buckets.items():
            if item in seen:
                continue
            s = hist[hist["item_id"] == item]["demand"].values
            if b in SBA_BUCKETS:
                preds.append((item, b, "sba", float(sba(s))))
            else:
                grp = items.loc[items["item_id"] == item, "group"].iloc[0]
                gmean = self.group_recent.get(grp, self.global_recent)
                obs = s[~np.isnan(s)]
                k = len(obs)
                if k > 0:
                    w = k / (k + 2.0)
                    val = w * obs[-4:].mean() + (1.0 - w) * gmean
                else:
                    val = gmean
                preds.append((item, b, "group_cold_start", float(val)))
        return pd.DataFrame(preds, columns=["item_id", "bucket", "method", "y_pred"])


def _placeholder(items, member_items, week, date):
    sub = items[items["item_id"].isin(member_items)][["item_id"]].copy()
    sub["week_index"] = week
    sub["demand"] = np.nan
    sub["date"] = date
    return sub
