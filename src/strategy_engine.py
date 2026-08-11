"""
Backtest engine for the intraday Brent-WTI mean-reversion strategy.

At each eligible 1-minute bar, the engine:

1. Computes the spread's rolling deviation from its recent mean.
2. Tests whether the rolling spread window is stationary.
3. Estimates whether the spread's half-life is short enough.
4. Enters a long or short spread position when all enabled entry gates pass.
5. Tracks the position until a mean-reversion exit, stop-loss, time-stop,
   or end-of-session exit is triggered.

The strategy uses the synthetic CL-BZ spread from the cleaned aligned dataset.

Output:
    OUTPUT_DIR / "brent_wti_strategy_1m.parquet"

Usage:
    python src/strategy_engine.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.stattools import adfuller, kpss
import statsmodels.api as sm

from clean_mbp1 import load_aligned, regime_key
from settings import config


# ---------------------------------------------------------------------
# Paths and dataset configuration
# ---------------------------------------------------------------------

DATA_DIR = config("DATA_DIR")
OUTPUT_DIR = config("OUTPUT_DIR")

FREQ = "1m"
RESULTS_PARQUET_NAME = "brent_wti_strategy_1m.parquet"


# ---------------------------------------------------------------------
# Default strategy parameters
# ---------------------------------------------------------------------

DEFAULT_WINDOW = 30
DEFAULT_DEVIATION_THRESHOLD = 2.5
DEFAULT_HALF_LIFE_THRESHOLD = 15.0
DEFAULT_EXIT_THRESHOLD = 0.5
DEFAULT_STOP_LOSS = 1000
DEFAULT_TIME_STOP = 30

MIN_STD = 1e-12


# ---------------------------------------------------------------------
# Entry-test configuration
# ---------------------------------------------------------------------

USE_ADF = True
USE_KPSS = True

ADF_ALPHA = 0.05
KPSS_ALPHA = 0.05

# ---------------------------------------------------------------------
# Backtest output schema
# ---------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "synth_mid",
    "ls_bid",
    "ls_ask",
    "rolling_mean",
    "rolling_std",
    "zscore",
    "halflife",
    "long_entry",
    "short_entry",
    "position",
    "entry_price",
    "exit_flag",
    "exit_reason",
    "position_age",
    "position_pnl",
    "step_pnl",
    "cum_pnl",
]


def results_path() -> Path:
    """Return the path used for the saved strategy results."""
    return OUTPUT_DIR / RESULTS_PARQUET_NAME


def prepare_data(data: pd.DataFrame | None) -> pd.DataFrame:
    if data is None:
        data = load_aligned(FREQ)

    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError("Strategy data must use a DatetimeIndex")

    if data.index.has_duplicates:
        raise ValueError("Strategy data contains duplicate timestamps")

    data = data.sort_index().copy()

    data = data.between_time("00:00", "19:59")

    data["regime"] = regime_key(data)

    data["eligible"] = (
        data["synth_mid"].notna()
        & data["ls_mid"].notna()
        & data["cl_mid"].notna()
        & data["bz_mid"].notna()
        & data["cl_instrument_id"].notna()
        & data["bz_instrument_id"].notna()
        & data["cl_n_events"].fillna(0).gt(0)
        & data["bz_n_events"].fillna(0).gt(0)
    )

    return data


def deviation_test(
    spread_mid: float,
    rolling_mean: float,
    rolling_std: float,
    deviation_threshold: float
) -> tuple[bool, int, float]:
    """Detect deviations above the set threshold."""
    if (
        pd.isna(spread_mid)
        or pd.isna(rolling_mean)
        or pd.isna(rolling_std)
        or rolling_std <= MIN_STD
    ):
        return False, 0, np.nan

    zscore = (spread_mid - rolling_mean) / rolling_std
    test_pass = False
    position = 0

    if zscore >= deviation_threshold:
        test_pass = True
        position = -1 # Short

    if zscore <= -deviation_threshold:
        test_pass = True
        position = 1 # Long

    return test_pass, position, zscore


def stationarity_test(
        rolling_window: pd.Series,
        use_adf: bool = USE_ADF,
        use_kpss: bool = USE_KPSS,
) -> bool:
    """Run the toggled stationarity tests to determine whether there is evidence for mean reversion."""
    rolling_window = rolling_window.dropna()

    if len(rolling_window) < 5 or rolling_window.nunique() < 3:
        return False
    
    test_results = []

    if use_adf:
        try:
            if len(rolling_window) < 20:
                adf_pvalue = adfuller(
                    rolling_window,
                    maxlag=0,
                    autolag=None,
                )[1]
            else:
                adf_pvalue = adfuller(
                    rolling_window,
                    autolag="AIC",
                )[1]

            test_results.append(adf_pvalue < ADF_ALPHA)

        except Exception:
            return False

    if use_kpss:
        try:
            # A statistic outside KPSS's p-value lookup table warns and clips to
            # the nearest tabulated bound. On a 30-bar window that is common and
            # harmless -- a clipped p-value still lands on the correct side of
            # KPSS_ALPHA -- so the warning is suppressed to keep doit logs clean.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", InterpolationWarning)
                kpss_pvalue = kpss(
                    rolling_window,
                    regression="c",
                    nlags="auto",
                )[1]

            test_results.append(kpss_pvalue > KPSS_ALPHA)

        except Exception:
            return False
        
    if not test_results:
        return True
    
    return all(test_results)


def halflife_test(
        rolling_window: pd.Series,
        half_life_threshold: float
) -> tuple[bool, float]:
    """Estimate half-life and test whether it is short enough for entry."""
    rolling_window = rolling_window.dropna()

    if len(rolling_window) < 3 or rolling_window.nunique() < 3:
        return False, np.nan
    
    y = rolling_window.iloc[1:]
    x = rolling_window.shift(1).iloc[1:]
    x = sm.add_constant(x)

    try:
        model = sm.OLS(y, x).fit()
        phi = model.params.iloc[1]
    except Exception:
        return False, np.nan
    
    if not np.isfinite(phi) or phi <= 0 or phi >= 1:
        return False, np.nan

    half_life = -np.log(2) / np.log(phi)

    test_pass = 0 < half_life <= half_life_threshold

    return test_pass, half_life


def run_strategy(
    data: pd.DataFrame,
    window: int,
    deviation_threshold: float,
    halflife_threshold: float,
    exit_threshold: float,
    stop_loss: float,
    time_stop: int,
    contract_multiplier: float = 1000.0,
) -> pd.DataFrame:
    data = prepare_data(data)
    tracker = pd.DataFrame(index=data.index, columns=OUTPUT_COLUMNS)

    # Initialize current-step variables
    curr_synth_mid = np.nan
    curr_rolling_mean = np.nan
    curr_rolling_std = np.nan
    curr_zscore = np.nan
    curr_halflife = np.nan

    curr_position = 0  # 1 for long, -1 for short, 0 for flat
    curr_step_pnl = 0.0
    curr_cum_pnl = 0.0

    # Initialize active-position state variables
    position_active = False
    entry_price = np.nan
    entry_halflife = np.nan
    curr_position_pnl = 0.0
    curr_position_age = 0

    for i, (timestamp, time_step) in enumerate(data.iterrows()):
        curr_synth_mid = time_step["synth_mid"]
        curr_ls_bid = time_step["ls_bid_px_00"]
        curr_ls_ask = time_step["ls_ask_px_00"]

        curr_rolling_mean = np.nan
        curr_rolling_std = np.nan
        curr_zscore = np.nan
        curr_halflife = np.nan

        curr_step_pnl = 0.0
        long_entry = False
        short_entry = False
        exit_flag = False
        exit_reason = None

        # A session ends before a timestamp gap or at the end of the dataset.
        if i == len(data) - 1:
            is_session_end = True
        else:
            next_timestamp = data.index[i + 1]
            is_session_end = (
                next_timestamp - timestamp != pd.Timedelta(FREQ)
            )

        # Construct the current rolling window.
        window_start = max(0, i - window + 1)

        curr_window = data["synth_mid"].iloc[window_start:i + 1]
        curr_regimes = data["regime"].iloc[window_start:i + 1]
        curr_eligible = data["eligible"].iloc[window_start:i + 1]

        consecutive_bars = (
            curr_window.index.to_series()
            .diff()
            .dropna()
            .eq(pd.Timedelta(FREQ))
            .all()
        )

        valid_window = (
            len(curr_window) == window
            and curr_regimes.nunique() == 1
            and curr_eligible.all()
            and consecutive_bars
        )

        if valid_window:
            curr_rolling_mean = curr_window.mean()
            curr_rolling_std = curr_window.std(ddof=1)

            _, _, curr_zscore = deviation_test(
                curr_synth_mid,
                curr_rolling_mean,
                curr_rolling_std,
                deviation_threshold,
            )

        if position_active:
            # Calculate executable mark-to-market PnL.
            previous_position_pnl = curr_position_pnl

            if curr_position == 1 and pd.notna(curr_ls_bid):
                # Long spread: entered at ask, liquidated at bid.
                curr_position_pnl = (
                    curr_ls_bid - entry_price
                ) * contract_multiplier

            elif curr_position == -1 and pd.notna(curr_ls_ask):
                # Short spread: entered at bid, covered at ask.
                curr_position_pnl = (
                    entry_price - curr_ls_ask
                ) * contract_multiplier

            curr_step_pnl = (
                curr_position_pnl - previous_position_pnl
            )
            curr_cum_pnl += curr_step_pnl
            curr_position_age += 1

            # Mean-reversion exit
            if (
                pd.notna(curr_zscore)
                and abs(curr_zscore) <= exit_threshold
            ):
                exit_flag = True
                exit_reason = "mean_reversion"

            # Stop-loss exit
            elif curr_position_pnl <= -stop_loss:
                exit_flag = True
                exit_reason = "stop_loss"

            # Time-stop exit
            elif curr_position_age >= time_stop:
                exit_flag = True
                exit_reason = "time_stop"

            # Session-end or dataset-end exit
            elif is_session_end:
                exit_flag = True
                exit_reason = "session_end"

            # Position is closed at this step.
            if exit_flag:
                tracker.loc[timestamp] = {
                    "synth_mid": curr_synth_mid,
                    "ls_bid": curr_ls_bid,
                    "ls_ask": curr_ls_ask,
                    "rolling_mean": curr_rolling_mean,
                    "rolling_std": curr_rolling_std,
                    "zscore": curr_zscore,
                    "halflife": entry_halflife,
                    "long_entry": False,
                    "short_entry": False,
                    "position": curr_position,
                    "entry_price": entry_price,
                    "exit_flag": True,
                    "exit_reason": exit_reason,
                    "position_age": curr_position_age,
                    "position_pnl": curr_position_pnl,
                    "step_pnl": curr_step_pnl,
                    "cum_pnl": curr_cum_pnl,
                }

                position_active = False
                curr_position = 0
                entry_price = np.nan
                entry_halflife = np.nan
                curr_position_pnl = 0.0
                curr_position_age = 0

                continue

            # Position remains open at this step.
            tracker.loc[timestamp] = {
                "synth_mid": curr_synth_mid,
                "ls_bid": curr_ls_bid,
                "ls_ask": curr_ls_ask,
                "rolling_mean": curr_rolling_mean,
                "rolling_std": curr_rolling_std,
                "zscore": curr_zscore,
                "halflife": entry_halflife,
                "long_entry": False,
                "short_entry": False,
                "position": curr_position,
                "entry_price": entry_price,
                "exit_flag": False,
                "exit_reason": None,
                "position_age": curr_position_age,
                "position_pnl": curr_position_pnl,
                "step_pnl": curr_step_pnl,
                "cum_pnl": curr_cum_pnl,
            }

            continue

        else:
            # Test 1: Deviation
            deviation_pass = False
            proposed_position = 0

            if valid_window:
                (
                    deviation_pass,
                    proposed_position,
                    curr_zscore,
                ) = deviation_test(
                    curr_synth_mid,
                    curr_rolling_mean,
                    curr_rolling_std,
                    deviation_threshold,
                )

            if deviation_pass:
                # Test 2: Stationarity
                stationarity_pass = stationarity_test(curr_window)

                if stationarity_pass:
                    # Test 3: Half-life
                    (
                        halflife_pass,
                        curr_halflife,
                    ) = halflife_test(
                        curr_window,
                        halflife_threshold,
                    )

                    execution_price_available = (
                        proposed_position == 1
                        and pd.notna(curr_ls_ask)
                    ) or (
                        proposed_position == -1
                        and pd.notna(curr_ls_bid)
                    )

                    # Do not enter on the final bar of a session.
                    if (
                        halflife_pass
                        and execution_price_available
                        and not is_session_end
                    ):
                        position_active = True
                        curr_position = proposed_position

                        if curr_position == 1:
                            entry_price = curr_ls_ask
                        else:
                            entry_price = curr_ls_bid

                        entry_halflife = curr_halflife
                        curr_position_pnl = 0.0
                        curr_position_age = 0

                        long_entry = curr_position == 1
                        short_entry = curr_position == -1

                        tracker.loc[timestamp] = {
                            "synth_mid": curr_synth_mid,
                            "ls_bid": curr_ls_bid,
                            "ls_ask": curr_ls_ask,
                            "rolling_mean": curr_rolling_mean,
                            "rolling_std": curr_rolling_std,
                            "zscore": curr_zscore,
                            "halflife": curr_halflife,
                            "long_entry": long_entry,
                            "short_entry": short_entry,
                            "position": curr_position,
                            "entry_price": entry_price,
                            "exit_flag": False,
                            "exit_reason": None,
                            "position_age": curr_position_age,
                            "position_pnl": curr_position_pnl,
                            "step_pnl": curr_step_pnl,
                            "cum_pnl": curr_cum_pnl,
                        }

                        continue

            # No position is entered at this step.
            tracker.loc[timestamp] = {
                "synth_mid": curr_synth_mid,
                "ls_bid": curr_ls_bid,
                "ls_ask": curr_ls_ask,
                "rolling_mean": curr_rolling_mean,
                "rolling_std": curr_rolling_std,
                "zscore": curr_zscore,
                "halflife": curr_halflife,
                "long_entry": False,
                "short_entry": False,
                "position": 0,
                "entry_price": np.nan,
                "exit_flag": False,
                "exit_reason": None,
                "position_age": 0,
                "position_pnl": 0.0,
                "step_pnl": 0.0,
                "cum_pnl": curr_cum_pnl,
            }

    return tracker


def main():
    """Backtest the default parameters on the cleaned 1m dataset and save it."""
    results = run_strategy(
        data=load_aligned(FREQ),
        window=DEFAULT_WINDOW,
        deviation_threshold=DEFAULT_DEVIATION_THRESHOLD,
        halflife_threshold=DEFAULT_HALF_LIFE_THRESHOLD,
        exit_threshold=DEFAULT_EXIT_THRESHOLD,
        stop_loss=DEFAULT_STOP_LOSS,
        time_stop=DEFAULT_TIME_STOP,
    )

    path = results_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    results.to_parquet(path)

    entries = int(results["long_entry"].sum() + results["short_entry"].sum())
    print(
        f"saved {path}: {len(results):,} bars, {entries} entries, "
        f"cumulative PnL {results['cum_pnl'].ffill().fillna(0).iloc[-1]:,.2f}"
    )


if __name__ == "__main__":
    main()
