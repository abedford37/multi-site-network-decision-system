"""Network nodes described by function, not by real building names.

Three functional roles cover any distribution network of this shape:
  INBOUND_CROSSDOCK : where containers arrive and are unloaded (a 3PL dock).
  STORAGE_RESERVE   : holds safety stock and excess; not customer facing.
  FORWARD_FULFILL   : ships to customers; the buildings containers are pulled to.

Forward buildings are distinguished by capability (which items they are built to
hold and ship), never by name. A real deployment maps its own sites onto these
roles through configuration; nothing here hardcodes a specific warehouse.
"""
from __future__ import annotations

from dataclasses import dataclass

INBOUND_CROSSDOCK = "inbound_crossdock"
STORAGE_RESERVE = "storage_reserve"
FORWARD_FULFILL = "forward_fulfill"


@dataclass(frozen=True)
class Building:
    name: str
    role: str
    size_pref: str          # "small" or "large": the size class this building is built for
    parcel: bool            # whether it handles parcel-eligible flow


# Default demo forward buildings: one small/parcel, one bulk/wholesale.
DEFAULT_FORWARD = [
    Building("FWD-A", FORWARD_FULFILL, size_pref="small", parcel=True),
    Building("FWD-B", FORWARD_FULFILL, size_pref="large", parcel=False),
]
