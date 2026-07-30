"""Tests for the issue-13 entry signal generator (pure functions, no network)."""

import numpy as np
import pandas as pd
import pytest

from signal_generator import (
    DEFAULT_ENTRY_Z,
    DEFAULT_WINDOW,
    generate_signal_at,
    generate_signals,
    signals_from_aligned,
)


def _idx(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-06-01", periods=n, freq="1min", tz="UTC")


def _noise_then_spike(n: int, spike: float, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    values = rng.normal(0.0, 0.1, size=n)
    values[-1] = spike
    return pd.Series(values, index=_idx(n), name="synth_mid")


def test_default_window_is_thirty():
    assert DEFAULT_WINDOW == 30


def test_invalid_window_and_entry_z_raise():
    series = _noise_then_spike(40, spike=3.0)
    with pytest.raises(ValueError, match="window must be >= 2"):
        generate_signals(series, window=1)
    with pytest.raises(ValueError, match="entry_z must be positive"):
        generate_signals(series, entry_z=0.0)
    with pytest.raises(ValueError, match="entry_z must be positive"):
        generate_signals(series, entry_z=-1.0)


def test_point_api_missing_timestamp_raises():
    series = _noise_then_spike(40, spike=3.0)
    missing = series.index[-1] + pd.Timedelta(minutes=1)
    with pytest.raises(KeyError, match="not in signal index"):
        generate_signal_at(series, missing)


def test_warmup_suppresses_signals_until_min_periods():
    n = DEFAULT_WINDOW + 5
    series = pd.Series(np.linspace(-1, 1, n), index=_idx(n))
    out = generate_signals(series, window=DEFAULT_WINDOW)
    # First `window` bars lack a full past window after shift(1).
    assert not out["valid"].iloc[:DEFAULT_WINDOW].any()
    assert (out["signal"].iloc[:DEFAULT_WINDOW] == 0).all()
    assert out["rolling_mean"].iloc[: DEFAULT_WINDOW - 1].isna().all()


def test_no_lookahead_in_rolling_stats():
    n = 80
    window = 10
    # Alternating past so σ > 0; spike only on the final bar.
    values = np.tile([0.0, 1.0], n // 2)
    values[-1] = 100.0
    series = pd.Series(values, index=_idx(n))
    out = generate_signals(series, window=window)

    past = series.iloc[-(window + 1) : -1]
    assert out["rolling_mean"].iloc[-1] == pytest.approx(past.mean())
    assert out["rolling_std"].iloc[-1] == pytest.approx(past.std(ddof=1))
    # Including the spike would pull the mean far above the past mean.
    assert out["rolling_mean"].iloc[-1] < 10.0

    # Changing only bar t must not change μ_t, σ_t.
    mutated = series.copy()
    mutated.iloc[-1] = -999.0
    out2 = generate_signals(mutated, window=window)
    assert out2["rolling_mean"].iloc[-1] == out["rolling_mean"].iloc[-1]
    assert out2["rolling_std"].iloc[-1] == out["rolling_std"].iloc[-1]


def test_threshold_short_and_long_entries():
    short_series = _noise_then_spike(120, spike=5.0)
    short_out = generate_signals(short_series, window=DEFAULT_WINDOW, entry_z=2.0)
    assert short_out["short_entry"].iloc[-1]
    assert short_out["signal"].iloc[-1] == -1
    assert not short_out["long_entry"].iloc[-1]

    long_series = _noise_then_spike(120, spike=-5.0, seed=1)
    long_out = generate_signals(long_series, window=DEFAULT_WINDOW, entry_z=2.0)
    assert long_out["long_entry"].iloc[-1]
    assert long_out["signal"].iloc[-1] == 1
    assert not long_out["short_entry"].iloc[-1]


def test_hygiene_blocks_nan_roll_carryforward_and_zero_std():
    n = 80
    idx = _idx(n)
    rng = np.random.default_rng(2)
    spread = rng.normal(0.0, 0.2, size=n)
    spread[-1] = 5.0
    frame = pd.DataFrame(
        {
            "synth_mid": spread,
            "cl_mid": 70.0,
            "bz_mid": 70.0 - spread,
            "is_roll_date": False,
            "cl_n_events": 1,
            "bz_n_events": 1,
        },
        index=idx,
    )

    # Baseline: last bar should short-enter.
    base = generate_signals(frame, window=DEFAULT_WINDOW)
    assert base["short_entry"].iloc[-1]

    # NaN spread
    bad = frame.copy()
    bad.loc[idx[-1], "synth_mid"] = np.nan
    assert not generate_signals(bad, window=DEFAULT_WINDOW)["short_entry"].iloc[-1]

    # NaN leg
    bad = frame.copy()
    bad.loc[idx[-1], "cl_mid"] = np.nan
    assert not generate_signals(bad, window=DEFAULT_WINDOW)["short_entry"].iloc[-1]

    # Roll date column on frame
    bad = frame.copy()
    bad.loc[idx[-1], "is_roll_date"] = True
    assert not generate_signals(bad, window=DEFAULT_WINDOW)["short_entry"].iloc[-1]

    # Explicit is_roll_date Series arg
    roll = pd.Series(False, index=idx)
    roll.iloc[-1] = True
    assert not generate_signals(
        frame.drop(columns=["is_roll_date"]),
        window=DEFAULT_WINDOW,
        is_roll_date=roll,
    )["short_entry"].iloc[-1]

    # Carry-forward (no events on a leg)
    bad = frame.copy()
    bad.loc[idx[-1], "bz_n_events"] = 0
    assert not generate_signals(bad, window=DEFAULT_WINDOW)["short_entry"].iloc[-1]

    # Flat history → σ ≈ 0
    flat = frame.copy()
    flat["synth_mid"] = 1.0
    flat.loc[idx[-1], "synth_mid"] = 10.0
    flat_out = generate_signals(flat, window=DEFAULT_WINDOW)
    assert not flat_out["valid"].iloc[-1]
    assert flat_out["signal"].iloc[-1] == 0


def test_is_stationary_mask_suppresses_entry():
    series = _noise_then_spike(120, spike=5.0)
    mask = pd.Series(True, index=series.index)
    mask.iloc[-1] = False
    out = generate_signals(series, window=DEFAULT_WINDOW, is_stationary=mask)
    assert out["zscore"].iloc[-1] > DEFAULT_ENTRY_Z
    assert not out["short_entry"].iloc[-1]
    assert out["signal"].iloc[-1] == 0
    assert not out["valid"].iloc[-1]


def test_point_api_matches_vectorized_row():
    series = _noise_then_spike(100, spike=-4.0, seed=3)
    ts = series.index[-1]
    row = generate_signal_at(series, ts, window=40, entry_z=2.0)
    full = generate_signals(series, window=40, entry_z=2.0)
    expected = full.loc[ts].to_dict()
    assert row.keys() == expected.keys()
    for key, value in expected.items():
        if pd.isna(value):
            assert pd.isna(row[key])
        else:
            assert row[key] == pytest.approx(value) if isinstance(value, float) else row[key] == value


def test_signals_from_aligned_matches_generate_signals():
    series = _noise_then_spike(90, spike=3.0)
    frame = series.to_frame("synth_mid")
    frame["is_roll_date"] = False
    via_aligned = signals_from_aligned(frame, window=DEFAULT_WINDOW)
    via_generate = generate_signals(frame, window=DEFAULT_WINDOW)
    pd.testing.assert_frame_equal(via_aligned, via_generate)


def test_dataframe_spread_col_and_output_schema():
    series = _noise_then_spike(90, spike=3.0)
    frame = series.to_frame("synth_mid")
    out = generate_signals(frame, spread_col="synth_mid", window=DEFAULT_WINDOW)
    assert list(out.columns) == [
        "spread",
        "rolling_mean",
        "rolling_std",
        "zscore",
        "entry_threshold",
        "long_entry",
        "short_entry",
        "signal",
        "valid",
    ]
    assert (out["entry_threshold"] == DEFAULT_ENTRY_Z).all()
