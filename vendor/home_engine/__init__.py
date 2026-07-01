"""Home assignment engine: slot active items into forward buildings under cube
capacity to minimize demand-weighted fulfillment cost, with ranked fallback homes,
while dead and slow items are parked in storage with no policy."""
from .nodes import default_locations
from .regions import distance_matrix
from .classify import classify_movement
from .data import generate, forward_view
from .cost import cost_matrix
from .assign import assign_items
from .evaluate import compare
from .pipeline import assign_homes

__all__ = ["default_locations", "distance_matrix", "classify_movement", "generate",
           "forward_view", "cost_matrix", "assign_items", "compare", "assign_homes"]
