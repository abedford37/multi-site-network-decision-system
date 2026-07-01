"""Demand forecasting engine: classify demand by pattern, route each bucket to
the method built for it, and evaluate honestly by walking forward in time."""
from .classify import classify_item, adi, cv2, ROUTING, ADI_CUT, CV2_CUT
from .pipeline import DemandForecaster
from .evaluate import walk_forward, metrics
from .data import generate

__all__ = ["classify_item", "adi", "cv2", "ROUTING", "ADI_CUT", "CV2_CUT",
           "DemandForecaster", "walk_forward", "metrics", "generate"]
