import sys, pathlib, warnings
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))
warnings.filterwarnings("ignore")

import pytest
from msdn import run_pipeline


@pytest.fixture(scope="session")
def state():
    return run_pipeline(seed=42)
