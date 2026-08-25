"""Test inputs, and a hard line between synthetic and real data.

The market snapshot is not distributed: it derives from a vendor whose terms
restrict redistribution. Most of the suite does not need it. A test that the
feature matrix contains no look-ahead, or that an active session pays a full round
trip, is a statement about the code and holds on any input with the right shape.

`market_frame` supplies that input. It prefers a real snapshot when the user has
obtained one, and otherwise returns the committed synthetic fixture, which is a
seeded random walk starting at exactly 100.00 and is obviously not market data.

**`load_snapshot()` is not given the same fallback**, deliberately. A research run
that silently used invented prices and reported a Sharpe ratio would be far worse
than one that refused to start.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SYNTHETIC = ROOT / "tests" / "fixtures" / "market_inputs_synthetic.csv"


def _real_snapshot() -> Path | None:
    found = sorted((ROOT / "data").glob("market_inputs_*.csv"))
    return found[-1] if found else None


@pytest.fixture(scope="session")
def market_frame() -> pd.DataFrame:
    path = _real_snapshot() or SYNTHETIC
    return pd.read_csv(path, index_col="Date", parse_dates=True)


@pytest.fixture(scope="session")
def using_real_market_data() -> bool:
    return _real_snapshot() is not None


@pytest.fixture(scope="session")
def rate_frame() -> pd.DataFrame:
    """Federal Reserve Board H.15 rates: public domain, committed, always real."""
    files = sorted((ROOT / "data").glob("treasury_rates_h15_*.csv"))
    if not files:
        pytest.skip("no Board rate file present")
    return pd.read_csv(files[-1], index_col="Date", parse_dates=True)


def requires_real_market_data(reason: str = ""):
    """Mark a test that cannot run without a snapshot the user must obtain."""
    return pytest.mark.skipif(
        _real_snapshot() is None,
        reason=("needs a market snapshot, which this repository does not distribute; "
                "run scripts/freeze_market_data.py to obtain one. " + reason).strip(),
    )
