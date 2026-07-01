"""Put the vendored engine libraries on the import path.

The MSDN package bundles the five engines under vendor/ so it is self-contained.
This module adds that directory to sys.path the first time MSDN is imported, so
`import demand_engine`, `inventory_policy`, and the rest resolve.
"""
from __future__ import annotations

import pathlib
import sys

_VENDOR = pathlib.Path(__file__).resolve().parents[2] / "vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))
