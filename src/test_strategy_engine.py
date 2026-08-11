"""Tests for the strategy backtest engine (pure functions, no network).

The three entry gates are tested directly. The position/exit state machine is
tested with the stationarity and half-life gates stubbed, so a scenario turns on
the prices it is built from rather than on whether a 30-bar ADF happens to
reject.
"""

import warnings

import numpy as np
import pandas as pd
import pytest
from statsmodels.tools.sm_exceptions import InterpolationWarning

import strategy_engine
from strategy_engine import (
    DEFAULT_HALF_LIFE_THRESHOLD,
    DEFAULT_WINDOW,
    OUTPUT_COLUMNS,
    RESULTS_PARQUET_NAME,
    deviation_test,
    halflife_test,
    prepare_data,
    results_path,
    run_strategy,
    stationarity_test,
)


HALF_SPREAD = 0.005
MULTIPLIER = 1000.0


def _idx(n: int, start: str = "2026-06-01 00:00") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="1min", tz="UTC")


def _ar1(n: int, phi: float, seed: int = 0, scale: float = 1.0) -> pd.Series:
    """AR(1) path around zero, so the half-life is -ln(2)/ln(phi)."""
    rng = np.random.default_rng(seed)
    shocks = rng.normal(0.0, scale, size=n)
    values = np.empty(n)
    values[0] = shocks[0]
    for i in range(1, n):
        values[i] = phi * values[i - 1] + shocks[i]
    return pd.Series(values, index=_idx(n))


def _aligned(spread: pd.Series, cl_id: int = 1, bz_id: int = 2) -> pd.DataFrame:
    """Minimal aligned frame with every column prepare_data/run_strategy read."""
    return pd.DataFrame(
        {
            "synth_mid": spread,
            "ls_mid": spread,
            "ls_bid_px_00": spread - HALF_SPREAD,
            "ls_ask_px_00": spread + HALF_SPREAD,
            "cl_mid": 70.0,
            "bz_mid": 70.0 - spread,
            "cl_instrument_id": cl_id,
            "bz_instrument_id": bz_id,
            "cl_n_events": 1,
            "bz_n_events": 1,
        },
        index=spread.index,
    )


def _baseline(n: int, level: float = 0.0) -> np.ndarray:
    """Two-valued sawtooth: nonzero rolling sigma without any trend."""
    return level + np.tile([0.0, 0.2], (n + 1) // 2)[:n]


def _stub_gates(monkeypatch, stationary: bool = True, halflife: float = 3.0):
    """Force the stationarity and half-life gates to a known verdict."""
    monkeypatch.setattr(
        strategy_engine, "stationarity_test", lambda *a, **kw: stationary
    )
    monkeypatch.setattr(
        strategy_engine, "halflife_test", lambda *a, **kw: (True, halflife)
    )


def _run(frame: pd.DataFrame, **overrides) -> pd.DataFrame:
    params = {
        "window": 10,
        "deviation_threshold": 2.0,
        "halflife_threshold": DEFAULT_HALF_LIFE_THRESHOLD,
        "exit_threshold": 0.5,
        "stop_loss": 1e9,
        "time_stop": 10_000,
    }
    params.update(overrides)
    return run_strategy(data=frame, **params)


# ---------------------------------------------------------------------
# Paths and defaults
# ---------------------------------------------------------------------


def test_results_path_uses_expected_filename():
    assert results_path().name == RESULTS_PARQUET_NAME == "brent_wti_strategy_1m.parquet"


def test_default_window_is_thirty():
    assert DEFAULT_WINDOW == 30


# ---------------------------------------------------------------------
# Test 1: deviation
# ---------------------------------------------------------------------


def test_deviation_short_above_threshold_and_long_below():
    passed, position, zscore = deviation_test(12.0, 10.0, 0.5, 2.0)
    assert passed and position == -1
    assert zscore == pytest.approx(4.0)

    passed, position, zscore = deviation_test(8.0, 10.0, 0.5, 2.0)
    assert passed and position == 1
    assert zscore == pytest.approx(-4.0)


def test_deviation_inside_threshold_reports_zscore_without_signal():
    passed, position, zscore = deviation_test(10.5, 10.0, 0.5, 2.0)
    assert not passed
    assert position == 0
    assert zscore == pytest.approx(1.0)


def test_deviation_at_threshold_is_inclusive():
    passed, position, _ = deviation_test(11.0, 10.0, 0.5, 2.0)
    assert passed and position == -1


def test_deviation_rejects_nan_inputs_and_degenerate_sigma():
    for args in (
        (np.nan, 10.0, 0.5, 2.0),
        (12.0, np.nan, 0.5, 2.0),
        (12.0, 10.0, np.nan, 2.0),
        (12.0, 10.0, 0.0, 2.0),
    ):
        passed, position, zscore = deviation_test(*args)
        assert not passed
        assert position == 0
        assert pd.isna(zscore)


# ---------------------------------------------------------------------
# Test 2: stationarity
# ---------------------------------------------------------------------


def test_stationarity_rejects_short_or_near_constant_windows():
    assert not stationarity_test(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert not stationarity_test(pd.Series([1.0] * 40))
    assert not stationarity_test(pd.Series([1.0, 1.0, 2.0] * 15))


def test_stationarity_accepts_mean_reverting_and_rejects_random_walk():
    assert stationarity_test(_ar1(200, phi=0.2, seed=7))
    assert not stationarity_test(_ar1(200, phi=1.0, seed=7))


def test_stationarity_with_both_tests_disabled_passes():
    walk = _ar1(200, phi=1.0, seed=7)
    assert stationarity_test(walk, use_adf=False, use_kpss=False)
    assert not stationarity_test(walk, use_adf=True, use_kpss=False)


def test_stationarity_ignores_nans_in_the_window():
    series = _ar1(200, phi=0.2, seed=7)
    with_gaps = series.copy()
    with_gaps.iloc[::10] = np.nan
    assert stationarity_test(with_gaps) == stationarity_test(series.dropna())


def test_stationarity_does_not_leak_kpss_interpolation_warnings():
    # KPSS clips an out-of-table statistic and warns; on a 30-bar window that is
    # routine, so the engine silences it rather than burying the doit log.
    window = _ar1(DEFAULT_WINDOW, phi=0.05, seed=3)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        stationarity_test(window)

    assert not [w for w in caught if issubclass(w.category, InterpolationWarning)]


# ---------------------------------------------------------------------
# Test 3: half-life
# ---------------------------------------------------------------------


def test_halflife_matches_the_ar1_coefficient_it_was_built_from():
    phi = 0.5
    passed, half_life = halflife_test(_ar1(2000, phi=phi, seed=11), 15.0)
    assert passed
    assert half_life == pytest.approx(-np.log(2) / np.log(phi), rel=0.25)


def test_halflife_rejects_non_reverting_phi_outright():
    # A noiseless explosive path estimates phi > 1 exactly, so there is no
    # half-life to report at all.
    explosive = pd.Series(1.05 ** np.arange(50), index=_idx(50))
    passed, half_life = halflife_test(explosive, 15.0)
    assert not passed
    assert pd.isna(half_life)


def test_halflife_rejects_reversion_slower_than_the_threshold():
    # A sampled random walk estimates phi just under 1, which is a valid but
    # far-too-slow half-life -- it must fail on the threshold, not the guard.
    passed, half_life = halflife_test(_ar1(2000, phi=1.0, seed=11), 15.0)
    assert not passed
    assert half_life > 15.0

    passed, half_life = halflife_test(_ar1(4000, phi=0.99, seed=11), 15.0)
    assert not passed
    assert half_life > 15.0


def test_halflife_rejects_short_or_constant_windows():
    for series in (pd.Series([1.0, 2.0]), pd.Series([3.0] * 50)):
        passed, half_life = halflife_test(series, 15.0)
        assert not passed
        assert pd.isna(half_life)


# ---------------------------------------------------------------------
# prepare_data
# ---------------------------------------------------------------------


def test_prepare_data_requires_a_unique_datetime_index():
    spread = pd.Series(_baseline(20))
    with pytest.raises(TypeError, match="DatetimeIndex"):
        prepare_data(_aligned(spread).reset_index(drop=True))

    dated = _aligned(pd.Series(_baseline(20), index=_idx(20)))
    duplicated = pd.concat([dated, dated.iloc[[0]]])
    with pytest.raises(ValueError, match="duplicate timestamps"):
        prepare_data(duplicated)


def test_prepare_data_drops_the_2000_2359_utc_hours():
    index = _idx(24 * 60)
    prepared = prepare_data(_aligned(pd.Series(_baseline(len(index)), index=index)))
    assert prepared.index.max().time() == pd.Timestamp("19:59").time()
    assert len(prepared) == 20 * 60


def test_prepare_data_flags_regimes_and_ineligible_bars():
    index = _idx(10)
    frame = _aligned(pd.Series(_baseline(10), index=index))
    frame.loc[index[3], "bz_instrument_id"] = 99
    frame.loc[index[5], "cl_n_events"] = 0
    frame.loc[index[6], "synth_mid"] = np.nan

    prepared = prepare_data(frame)

    assert prepared["regime"].nunique() == 2
    assert prepared["eligible"].iloc[[0, 1, 2, 3, 4, 7, 8, 9]].all()
    assert not prepared["eligible"].iloc[[5, 6]].any()


# ---------------------------------------------------------------------
# run_strategy: schema and gating
# ---------------------------------------------------------------------


def test_run_strategy_returns_one_row_per_eligible_bar_in_schema_order():
    frame = _aligned(pd.Series(_baseline(40), index=_idx(40)))
    results = _run(frame)
    assert list(results.columns) == OUTPUT_COLUMNS
    assert results.index.equals(frame.index)


def test_run_strategy_leaves_the_warmup_window_flat():
    frame = _aligned(pd.Series(_baseline(40), index=_idx(40)))
    results = _run(frame, window=10)
    assert results["rolling_mean"].iloc[:9].isna().all()
    assert results["zscore"].iloc[:9].isna().all()
    assert (results["position"] == 0).all()


def test_run_strategy_takes_no_trade_without_a_deviation(monkeypatch):
    _stub_gates(monkeypatch)
    frame = _aligned(pd.Series(_baseline(40), index=_idx(40)))
    results = _run(frame)
    assert not results["long_entry"].any()
    assert not results["short_entry"].any()
    assert results["cum_pnl"].iloc[-1] == 0.0


def test_run_strategy_shorts_an_upward_spike_at_the_bid(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(40)
    values[20] = 5.0
    index = _idx(40)
    frame = _aligned(pd.Series(values, index=index))

    results = _run(frame)
    entry = results.loc[index[20]]

    assert entry["short_entry"] and not entry["long_entry"]
    assert entry["position"] == -1
    assert entry["zscore"] >= 2.0
    assert entry["entry_price"] == pytest.approx(5.0 - HALF_SPREAD)
    assert entry["halflife"] == 3.0


def test_run_strategy_longs_a_downward_spike_at_the_ask(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(40)
    values[20] = -5.0
    index = _idx(40)
    frame = _aligned(pd.Series(values, index=index))

    results = _run(frame)
    entry = results.loc[index[20]]

    assert entry["long_entry"] and not entry["short_entry"]
    assert entry["position"] == 1
    assert entry["zscore"] <= -2.0
    assert entry["entry_price"] == pytest.approx(-5.0 + HALF_SPREAD)


def test_run_strategy_blocks_entry_when_a_gate_fails(monkeypatch):
    _stub_gates(monkeypatch, stationary=False)

    values = _baseline(40)
    values[20] = 5.0
    frame = _aligned(pd.Series(values, index=_idx(40)))

    results = _run(frame)
    assert not results["short_entry"].any()
    assert (results["position"] == 0).all()


def test_run_strategy_blocks_entry_when_the_window_spans_a_roll(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(40)
    values[20] = 5.0
    index = _idx(40)
    frame = _aligned(pd.Series(values, index=index))
    # Roll the BZ leg inside the 10-bar window ending at the spike.
    frame.loc[index[15:], "bz_instrument_id"] = 3

    results = _run(frame)
    assert pd.isna(results.loc[index[20], "zscore"])
    assert not results["short_entry"].any()


def test_run_strategy_blocks_entry_when_a_leg_stops_trading(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(40)
    values[20] = 5.0
    index = _idx(40)
    frame = _aligned(pd.Series(values, index=index))
    frame.loc[index[18], "cl_n_events"] = 0

    results = _run(frame)
    assert not results["short_entry"].any()


# ---------------------------------------------------------------------
# run_strategy: exits and PnL
# ---------------------------------------------------------------------


def test_mean_reversion_exit_closes_the_trade_and_books_the_gain(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(40)
    values[20] = 5.0
    index = _idx(40)
    frame = _aligned(pd.Series(values, index=index))

    results = _run(frame, exit_threshold=0.5)
    exits = results[results["exit_flag"].astype(bool)]

    assert len(exits) == 1
    exit_row = exits.iloc[0]
    assert exit_row["exit_reason"] == "mean_reversion"
    assert abs(exit_row["zscore"]) <= 0.5

    entry_price = results.loc[index[20], "entry_price"]
    cover_price = frame.loc[exits.index[0], "ls_ask_px_00"]
    assert exit_row["position_pnl"] == pytest.approx(
        (entry_price - cover_price) * MULTIPLIER
    )
    assert results["cum_pnl"].iloc[-1] == pytest.approx(exit_row["position_pnl"])
    assert results["position"].iloc[-1] == 0


def test_stop_loss_exit_fires_when_the_spread_keeps_widening(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(40)
    values[20] = 5.0
    values[21:] = 6.0
    index = _idx(40)
    frame = _aligned(pd.Series(values, index=index))

    # exit_threshold=0 disables the mean-reversion exit, isolating the stop.
    results = _run(frame, exit_threshold=0.0, stop_loss=100.0)
    exits = results[results["exit_flag"].astype(bool)]

    assert exits.iloc[0]["exit_reason"] == "stop_loss"
    assert exits.iloc[0]["position_pnl"] <= -100.0
    assert results["cum_pnl"].iloc[-1] < 0


def test_time_stop_exit_fires_after_the_configured_number_of_bars(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(40)
    values[20] = 5.0
    values[21:] = 5.0
    index = _idx(40)
    frame = _aligned(pd.Series(values, index=index))

    results = _run(frame, exit_threshold=0.0, time_stop=3)
    exits = results[results["exit_flag"].astype(bool)]

    assert exits.iloc[0]["exit_reason"] == "time_stop"
    assert exits.iloc[0]["position_age"] == 3
    assert exits.index[0] == index[23]


def test_session_end_exit_closes_across_a_timestamp_gap(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(30)
    values[20] = 5.0
    index = _idx(30)
    # Drop bar 23, so bar 22 is the last bar of its session.
    kept = index.delete(23)
    frame = _aligned(pd.Series(np.delete(values, 23), index=kept))

    results = _run(frame, exit_threshold=0.0, time_stop=10_000)
    exits = results[results["exit_flag"].astype(bool)]

    assert exits.iloc[0]["exit_reason"] == "session_end"
    assert exits.index[0] == index[22]


def test_no_entry_on_the_final_bar_of_the_dataset(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(40)
    values[-1] = 5.0
    frame = _aligned(pd.Series(values, index=_idx(40)))

    results = _run(frame)
    assert not results["short_entry"].any()
    assert results["position"].iloc[-1] == 0


def test_cumulative_pnl_is_the_running_sum_of_step_pnl(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(60)
    values[20] = 5.0
    values[40] = -5.0
    frame = _aligned(pd.Series(values, index=_idx(60)))

    results = _run(frame)
    step = results["step_pnl"].astype(float).fillna(0.0)
    cumulative = results["cum_pnl"].astype(float)

    assert cumulative.iloc[-1] == pytest.approx(step.sum())
    pd.testing.assert_series_equal(
        cumulative, step.cumsum(), check_names=False, rtol=1e-9
    )


def test_only_one_position_is_held_at_a_time(monkeypatch):
    _stub_gates(monkeypatch)

    values = _baseline(120)
    for spike in (20, 40, 60, 80):
        values[spike] = 5.0
    frame = _aligned(pd.Series(values, index=_idx(120)))

    results = _run(frame)
    assert results["position"].astype(float).abs().max() <= 1
    n_entries = int(results["long_entry"].sum() + results["short_entry"].sum())
    assert n_entries == int(results["exit_flag"].sum())
