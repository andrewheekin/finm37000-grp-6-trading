"""Tests for the placeholder random strategy (issue #38).

All tests run on synthetic price series -- no Databento pull or cached
data required.
"""

import numpy as np
import pandas as pd
import pytest

from random_strategy import run_strategy


@pytest.fixture
def mid():
    idx = pd.date_range("2026-06-01 09:00", periods=500, freq="1min", tz="UTC")
    rng = np.random.default_rng(0)
    return pd.Series(50 + rng.normal(0, 0.05, len(idx)).cumsum(), index=idx, name="mid")


def test_same_seed_is_reproducible(mid):
    a = run_strategy(mid, seed=123)
    b = run_strategy(mid, seed=123)
    pd.testing.assert_frame_equal(a, b)


def test_positions_are_unit_or_flat(mid):
    out = run_strategy(mid)
    assert set(out["position"].unique()) <= {-1.0, 0.0, 1.0}


def test_all_three_actions_occur(mid):
    out = run_strategy(mid)
    assert set(out["action"].unique()) == {"buy", "sell", "hold"}


def test_hold_keeps_prior_position(mid):
    out = run_strategy(mid)
    held = out[out["action"] == "hold"]["position"]
    prior = out["position"].shift().loc[held.index].fillna(0.0)
    pd.testing.assert_series_equal(held, prior, check_names=False)


def test_buy_and_sell_set_target_position(mid):
    out = run_strategy(mid)
    assert (out.loc[out["action"] == "buy", "position"] == 1.0).all()
    assert (out.loc[out["action"] == "sell", "position"] == -1.0).all()


def test_bar_pnl_is_lagged_position_times_mid_change(mid):
    out = run_strategy(mid)
    expected = (out["position"].shift(1) * out["mid"].diff()).fillna(0.0)
    pd.testing.assert_series_equal(out["bar_pnl"], expected, check_names=False)
    assert out["bar_pnl"].iloc[0] == 0.0
    pd.testing.assert_series_equal(
        out["cum_pnl"], out["bar_pnl"].cumsum(), check_names=False
    )


def test_nan_mids_are_dropped(mid):
    gappy = mid.copy()
    gappy.iloc[100:150] = np.nan
    out = run_strategy(gappy)
    assert len(out) == len(mid) - 50
    assert out["mid"].notna().all()
