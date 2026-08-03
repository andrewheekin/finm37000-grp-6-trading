"""Entry signal generator for the Brent-WTI spread (issue #13).

For each bar, compute a trailing rolling mean and standard deviation of the
spread over the window ending at that bar (inclusive), form a z-score, and emit
long/short entry flags when |z| exceeds the entry threshold. Exits and position
state are out of scope (issue #15).

Defaults: 1-minute bars, 30-bar rolling window, symmetric ±2 entry bands.
An optional ``is_stationary`` mask suppresses entries outside stationary
windows. The production path builds this mask with the rolling ADF/KPSS test.

Usage:
    python src/signal_generator.py   # writes parquet to OUTPUT_DIR
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from clean_mbp1 import load_aligned
from rolling_stationarity import rolling_stationarity_test
from settings import config

OUTPUT_DIR = config("OUTPUT_DIR")

DEFAULT_WINDOW = 30
DEFAULT_ENTRY_Z = 2.0
# Std below this is treated as degenerate (div-by-zero / flat window).
MIN_STD = 1e-12

OUTPUT_COLUMNS = [
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

SIGNALS_PARQUET_NAME = "brent_wti_signals_1m.parquet"


def signals_path() -> Path:
    """Path for the entry-signals parquet under OUTPUT_DIR."""
    return OUTPUT_DIR / SIGNALS_PARQUET_NAME


def _extract_spread(
    data: pd.Series | pd.DataFrame, spread_col: str
) -> tuple[pd.Series, pd.DataFrame | None]:
    if isinstance(data, pd.Series):
        spread = data.rename("spread")
        return spread, None
    if spread_col not in data.columns:
        raise KeyError(f"spread column {spread_col!r} not in DataFrame")
    return data[spread_col].rename("spread"), data


def _hygiene_mask(
    frame: pd.DataFrame | None,
    spread: pd.Series,
    rolling_std: pd.Series,
    is_roll_date: pd.Series | None,
) -> pd.Series:
    """True where the bar is eligible for an entry (before stationarity)."""
    valid = spread.notna() & rolling_std.notna() & (rolling_std > MIN_STD)

    if is_roll_date is not None:
        roll = is_roll_date.reindex(spread.index)
        valid &= ~roll.fillna(False).astype(bool)
    elif frame is not None and "is_roll_date" in frame.columns:
        valid &= ~frame["is_roll_date"].fillna(False).astype(bool)

    if frame is None:
        return valid

    for col in ("cl_mid", "bz_mid"):
        if col in frame.columns:
            valid &= frame[col].notna()

    for col in ("cl_n_events", "bz_n_events"):
        if col in frame.columns:
            # Carry-forward buckets: activity is never ffilled, so 0 means stale.
            valid &= frame[col].fillna(0) > 0

    return valid


def build_stationarity_mask(
    data: pd.Series | pd.DataFrame,
    *,
    spread_col: str = "synth_mid",
    window: int = DEFAULT_WINDOW,
    step: int = 1,
) -> pd.Series:
    """Build an index-aligned rolling stationarity gate for signal generation.

    Missing timestamps, including the initial warm-up interval, are treated as
    non-stationary. Each rolling result is labeled at its window end, so the
    returned mask uses no future observations.
    """
    spread, _ = _extract_spread(data, spread_col)
    is_stationary = rolling_stationarity_test(
        spread,
        window=window,
        step=step,
    )["is_stationary"]
    return is_stationary.reindex(spread.index).fillna(False).astype(bool)


def generate_signals(
    data: pd.Series | pd.DataFrame,
    *,
    spread_col: str = "synth_mid",
    window: int = DEFAULT_WINDOW,
    entry_z: float = DEFAULT_ENTRY_Z,
    min_periods: int | None = None,
    is_roll_date: pd.Series | None = None,
    is_stationary: pd.Series | None = None,
) -> pd.DataFrame:
    """Vectorized entry signals from a spread Series or aligned DataFrame.

    Rolling mean/std at time t use the ``window`` bars ending at t, including the
    observation at t itself, which is known at decision time and so introduces no
    lookahead. Entries may re-fire on every breach; no position state is kept.

    Parameters
    ----------
    data
        Spread series, or aligned DataFrame containing ``spread_col`` (and
        optionally hygiene columns: ``cl_mid``, ``bz_mid``, ``is_roll_date``,
        ``cl_n_events``, ``bz_n_events``).
    spread_col
        Column name when ``data`` is a DataFrame. Ignored for Series input.
    window
        Rolling window length in bars (default 30 = 30 minutes on 1m data).
    entry_z
        Symmetric absolute z-score threshold for entries.
    min_periods
        Minimum observations for rolling stats; defaults to ``window``.
    is_roll_date
        Optional boolean Series; True suppresses entries. If omitted and
        ``data`` is a DataFrame with ``is_roll_date``, that column is used.
    is_stationary
        Optional boolean Series aligned to ``data``; False suppresses entries.

    Returns
    -------
    DataFrame with columns in ``OUTPUT_COLUMNS``, indexed like ``data``.
    """
    if window < 2:
        raise ValueError("window must be >= 2")
    if entry_z <= 0:
        raise ValueError("entry_z must be positive")
    if min_periods is None:
        min_periods = window

    spread, frame = _extract_spread(data, spread_col)
    roller = spread.rolling(window=window, min_periods=min_periods)
    rolling_mean = roller.mean()
    rolling_std = roller.std(ddof=1)

    zscore = (spread - rolling_mean) / rolling_std

    valid = _hygiene_mask(frame, spread, rolling_std, is_roll_date)
    if is_stationary is not None:
        stationary = is_stationary.reindex(spread.index)
        valid &= stationary.fillna(False).astype(bool)

    long_entry = valid & (zscore < -entry_z)
    short_entry = valid & (zscore > entry_z)

    signal = pd.Series(0, index=spread.index, dtype="int8")
    signal = signal.mask(long_entry, 1).mask(short_entry, -1)

    out = pd.DataFrame(
        {
            "spread": spread,
            "rolling_mean": rolling_mean,
            "rolling_std": rolling_std,
            "zscore": zscore,
            "entry_threshold": entry_z,
            "long_entry": long_entry.fillna(False),
            "short_entry": short_entry.fillna(False),
            "signal": signal,
            "valid": valid.fillna(False),
        },
        index=spread.index,
    )
    return out[OUTPUT_COLUMNS]


def generate_signal_at(
    data: pd.Series | pd.DataFrame,
    timestamp,
    **kwargs,
) -> dict:
    """Point API: return the ``generate_signals`` row at ``timestamp`` as a dict.

    Raises
    ------
    KeyError
        If ``timestamp`` is not in the data index.
    """
    out = generate_signals(data, **kwargs)
    if timestamp not in out.index:
        raise KeyError(
            f"timestamp {timestamp!r} not in signal index "
            f"[{out.index.min()} .. {out.index.max()}]"
        )
    return out.loc[timestamp].to_dict()


def signals_from_aligned(
    aligned: pd.DataFrame,
    *,
    spread_col: str = "synth_mid",
    **kwargs,
) -> pd.DataFrame:
    """Convenience wrapper over an aligned Brent-WTI DataFrame."""
    return generate_signals(aligned, spread_col=spread_col, **kwargs)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    aligned = load_aligned("1m")
    is_stationary = build_stationarity_mask(
        aligned,
        spread_col="synth_mid",
        window=DEFAULT_WINDOW,
        step=1,
    )
    signals = signals_from_aligned(aligned, is_stationary=is_stationary)
    path = signals_path()
    signals.to_parquet(path)
    n_long = int(signals["long_entry"].sum())
    n_short = int(signals["short_entry"].sum())
    n_valid = int(signals["valid"].sum())
    print(
        f"wrote {path.name}: {len(signals):,} bars, "
        f"{n_valid:,} valid, {n_long:,} long / {n_short:,} short entries"
    )


if __name__ == "__main__":
    main()
