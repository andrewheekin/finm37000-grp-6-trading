"""Tests for the issue-4 market-data pipeline (pure functions, no network).

Covers cache naming in pull_databento, event cleaning / gridding / roll
flagging / alignment in clean_mbp1, spread filtering in instrument_discovery,
and the rolling-deviation transform behind the diagnostics figures.
"""

import pandas as pd
import pytest

from clean_mbp1 import (
    FRONT_SPREAD,
    build_aligned,
    clean_events,
    mark_roll_dates,
    to_grid,
)
from instrument_discovery import find_cl_bz_spreads
from plot_spread_diagnostics import rolling_deviations
from pull_databento import DATABENTO_CACHE, _cache_path


def make_raw_events(timestamps, bids, asks, actions=None, sizes=None, instrument_ids=None):
    """Minimal raw MBP-1 frame with the columns clean_events consumes."""
    n = len(timestamps)
    return pd.DataFrame(
        {
            "instrument_id": instrument_ids if instrument_ids is not None else [101] * n,
            "action": actions if actions is not None else ["A"] * n,
            "side": ["B"] * n,
            "price": bids,
            "size": sizes if sizes is not None else [1] * n,
            "bid_px_00": bids,
            "ask_px_00": asks,
            "bid_sz_00": [5] * n,
            "ask_sz_00": [7] * n,
        },
        index=pd.DatetimeIndex(timestamps, tz="UTC"),
    )


def test_cache_path_encodes_symbol_schema_and_range():
    path = _cache_path("CL.v.0", "mbp-1", "2026-06-01", "2026-06-06")
    assert path.name == "glbx-mdp3_cl-v-0_mbp-1_2026-06-01_2026-06-06.dbn"
    assert path.parent == DATABENTO_CACHE


def test_clean_events_adds_mid_and_crossed_flag():
    raw = make_raw_events(
        ["2026-06-01 00:00:00", "2026-06-01 00:00:01"],
        bids=[10.0, 12.0],
        asks=[11.0, 11.5],
    )
    out = clean_events(raw)
    assert out["mid"].tolist() == [10.5, 11.75]
    assert out["is_crossed"].tolist() == [False, True]
    assert len(out) == len(raw)  # crossed rows are flagged, not dropped


def test_to_grid_takes_last_quote_and_counts_activity():
    raw = make_raw_events(
        [
            "2026-06-01 00:00:00.100",
            "2026-06-01 00:00:00.900",
            "2026-06-01 00:00:02.000",
        ],
        bids=[10.0, 10.5, 11.0],
        asks=[11.0, 11.5, 12.0],
        actions=["A", "T", "T"],
        sizes=[1, 3, 4],
    )
    grid = to_grid(clean_events(raw), "1s")

    t0 = pd.Timestamp("2026-06-01 00:00:00", tz="UTC")
    t1 = pd.Timestamp("2026-06-01 00:00:01", tz="UTC")
    t2 = pd.Timestamp("2026-06-01 00:00:02", tz="UTC")

    # Bucket 0: last of the two events wins; one of them is a trade.
    assert grid.loc[t0, "bid_px_00"] == 10.5
    assert grid.loc[t0, "n_events"] == 2
    assert grid.loc[t0, "n_trades"] == 1
    assert grid.loc[t0, "volume"] == 3

    # Bucket 1 has no events: quote is carried forward, activity is not.
    assert grid.loc[t1, "bid_px_00"] == 10.5
    assert grid.loc[t1, "n_events"] == 0
    assert grid.loc[t1, "n_trades"] == 0
    assert grid.loc[t1, "volume"] == 0

    assert grid.loc[t2, "bid_px_00"] == 11.0
    assert grid.loc[t2, "volume"] == 4


def test_to_grid_forward_fill_stops_at_limit():
    # On the 1m grid the ffill limit is 600s / 60s = 10 buckets.
    raw = make_raw_events(
        ["2026-06-01 00:00:30", "2026-06-01 00:15:30"],
        bids=[10.0, 11.0],
        asks=[11.0, 12.0],
    )
    grid = to_grid(clean_events(raw), "1m")
    filled_until = pd.Timestamp("2026-06-01 00:10", tz="UTC")
    first_gap = pd.Timestamp("2026-06-01 00:11", tz="UTC")
    assert grid.loc[filled_until, "bid_px_00"] == 10.0
    assert pd.isna(grid.loc[first_gap, "bid_px_00"])
    assert grid.loc[first_gap, "n_events"] == 0


def test_mark_roll_dates_flags_contract_change():
    idx = pd.DatetimeIndex(
        ["2026-06-01 12:00", "2026-06-02 12:00", "2026-06-03 12:00"], tz="UTC"
    )
    grid = pd.DataFrame({"instrument_id": [101, 101, 202]}, index=idx)
    flagged = mark_roll_dates(grid)
    assert flagged["is_roll_date"].tolist() == [False, False, True]


def test_build_aligned_synthetic_spread_and_roll_flag():
    idx = pd.DatetimeIndex(
        ["2026-06-01 00:00:00", "2026-06-01 00:00:01"], tz="UTC"
    )

    def leg(bids, asks, rolls):
        return pd.DataFrame(
            {
                "bid_px_00": bids,
                "ask_px_00": asks,
                "mid": [(b + a) / 2 for b, a in zip(bids, asks)],
                "is_roll_date": rolls,
            },
            index=idx,
        )

    grids = {
        ("CL.v.0", "1s"): leg([60.0, 60.5], [60.1, 60.6], [False, False]),
        ("BZ.v.0", "1s"): leg([64.0, 64.2], [64.1, 64.3], [False, True]),
        (FRONT_SPREAD, "1s"): leg([-4.1, -3.9], [-4.0, -3.8], [False, False]),
    }
    aligned = build_aligned(grids, "1s")

    # Tradeable synthetic: buy CL at ask / sell BZ at bid and vice versa.
    assert aligned["synth_bid"].iloc[0] == pytest.approx(60.0 - 64.1)
    assert aligned["synth_ask"].iloc[0] == pytest.approx(60.1 - 64.0)
    assert aligned["synth_mid"].iloc[0] == pytest.approx(60.05 - 64.05)
    # Roll flag is the OR of the two legs' flags.
    assert aligned["is_roll_date"].tolist() == [False, True]
    # Listed-spread columns arrive with the ls_ prefix.
    assert aligned["ls_bid_px_00"].iloc[0] == -4.1


def test_find_cl_bz_spreads_keeps_only_cross_product_spreads():
    definitions = pd.DataFrame(
        {
            "raw_symbol": ["CLN6", "CLN6-BZN6", "CLN6-CLQ6", "BZN6-BZQ6"],
            "instrument_class": ["F", "S", "S", "S"],
            "leg_count": [0, 2, 2, 2],
        }
    )
    out = find_cl_bz_spreads(definitions)
    assert out["raw_symbol"].tolist() == ["CLN6-BZN6"]


def test_rolling_deviations_zero_for_constant_series():
    idx = pd.date_range("2026-06-01", periods=240, freq="1min", tz="UTC")
    series = pd.Series(5.0, index=idx)
    dev = rolling_deviations(series, windows=["30min", "2h"])
    assert list(dev["window"].cat.categories) == ["30min", "2h"]
    assert (dev["deviation"] == 0).all()
    assert not dev["deviation"].isna().any()
