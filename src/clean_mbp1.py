"""Clean and align the MBP-1 pulls into reusable parquet datasets (issue #4).

Outputs, written under DATA_DIR/clean:

1. Per-instrument grids -- ``{symbol}_1s.parquet`` and ``{symbol}_1m.parquet``:
   last top-of-book quote per bucket (bid/ask/mid + sizes), forward-filled up
   to FFILL_LIMIT_S seconds, plus per-bucket activity columns (n_events,
   n_trades, volume) which are never forward-filled -- n_events == 0 marks a
   bucket whose quote is a carry-forward.
2. Spread event series -- ``{symbol}_events.parquet`` for the exchange-listed
   spread instruments only. These books ARE the tradeable Brent-WTI spread,
   so their raw (cleaned) event sequence is stored as-is; no grid needed for
   construction (see discussion in issue #4).
3. Aligned dataset -- ``brent_wti_aligned_{freq}.parquet``: CL and BZ leg
   grids side by side (cl_*/bz_* columns), the synthetic spread computed from
   them (synth_mid, and the tradeable synth_bid = cl_bid - bz_ask,
   synth_ask = cl_ask - bz_bid), and the front listed spread's book (ls_*)
   on the same index.

Roll handling (issue #20): every row keeps its underlying instrument_id, and
is_roll_date flags calendar dates on which an instrument's mapped contract
differs from the previous date's. Because the two legs roll on different
dates, the unit that must stay constant across a rolling window is the *pair*
of held contracts -- see regime_key and rolling_within_regime below. The
measurements behind that convention are in src/roll_analysis.py and the
"Contract rolls" section of data_manual/data_README.md.

Usage:
    python src/clean_mbp1.py
"""

import pandas as pd

from pull_databento import (
    OUTRIGHTS,
    PILOT_END,
    PILOT_START,
    SPREADS,
    load_mbp1,
)
from settings import config

DATA_DIR = config("DATA_DIR")
CLEAN_DIR = DATA_DIR / "clean"

# Forward-fill quotes across at most this many seconds; beyond it a bucket
# stays NaN (e.g. the daily maintenance break) rather than carrying a quote.
FFILL_LIMIT_S = 600

GRID_FREQS = {"1s": "1s", "1m": "1min"}
QUOTE_COLS = ["bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00", "mid", "instrument_id"]

FRONT_SPREAD = SPREADS[0]


def _safe(symbol: str) -> str:
    """
    >>> _safe("CL.v.0")
    'cl-v-0'
    """
    return symbol.replace(".", "-").replace(":", "-").lower()


def clean_events(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce raw MBP-1 events to the analysis columns.

    Keeps every event (including trades), adds mid and a crossed/locked-book
    flag rather than dropping rows -- downstream code decides what to exclude.
    """
    out = df[
        [
            "instrument_id",
            "action",
            "side",
            "price",
            "size",
            "bid_px_00",
            "ask_px_00",
            "bid_sz_00",
            "ask_sz_00",
        ]
    ].copy()
    out["mid"] = (out["bid_px_00"] + out["ask_px_00"]) / 2
    out["is_crossed"] = out["bid_px_00"] >= out["ask_px_00"]
    return out


def to_grid(events: pd.DataFrame, freq: str = "1s") -> pd.DataFrame:
    """Resample cleaned events to a fixed grid.

    Quote columns take the last value in each bucket and are forward-filled
    up to FFILL_LIMIT_S; activity columns are per-bucket and never filled.
    """
    rule = GRID_FREQS[freq]
    grid = events[QUOTE_COLS].resample(rule).last()

    seconds_per_bucket = pd.Timedelta(rule).total_seconds()
    limit = max(1, int(FFILL_LIMIT_S / seconds_per_bucket))
    grid = grid.ffill(limit=limit)

    grid["n_events"] = events["price"].resample(rule).size()
    trades = events[events["action"] == "T"]
    grid["n_trades"] = trades["price"].resample(rule).size().reindex(grid.index, fill_value=0)
    grid["volume"] = (
        trades["size"].resample(rule).sum().reindex(grid.index, fill_value=0)
    )
    return grid


def mark_roll_dates(grid: pd.DataFrame) -> pd.DataFrame:
    """Flag dates whose mapped contract differs from the previous date's."""
    grid = grid.copy()
    last_id_by_date = grid.groupby(grid.index.date)["instrument_id"].last()
    rolled = last_id_by_date != last_id_by_date.shift()
    rolled.iloc[0] = False
    roll_dates = set(last_id_by_date.index[rolled])
    grid["is_roll_date"] = pd.Series(grid.index.date, index=grid.index).isin(roll_dates)
    return grid


def regime_key(aligned: pd.DataFrame) -> pd.Series:
    """Identify the (CL contract, BZ contract) pair backing each row.

    CL and BZ roll on different dates, so neither leg's contract alone marks
    off a comparable stretch of the spread -- the pair does. A change in this
    key is exactly a point where the spread level shifts for a reason that is
    not a market move.
    """
    return (
        aligned["cl_instrument_id"].astype("Int64").astype(str)
        + "/"
        + aligned["bz_instrument_id"].astype("Int64").astype(str)
    )


def regime_blocks(regime: pd.Series) -> pd.Series:
    """Number each *contiguous* run of one regime key separately.

    Grouping on the key alone would merge every occurrence of a contract pair
    into one group, so a pair that recurs -- which is what a flip-back is,
    e.g. BZK6 -> BZM6 -> BZK6 five times in March 2026 -- would let a window
    reach back across the intervening contract as if it were continuous.
    Numbering runs instead makes each stretch its own group.

    >>> regime_blocks(pd.Series(["A", "A", "B", "A"])).tolist()
    [1, 1, 2, 3]
    """
    key = regime.astype(object)
    return key.ne(key.shift()).cumsum()


def rolling_within_regime(
    series: pd.Series,
    regime: pd.Series,
    window: int | str,
    min_periods: int | None = None,
    stat: str = "mean",
    require_full_window: bool = True,
) -> pd.Series:
    """Trailing statistic that never draws on a different contract pair.

    Equivalent to restarting the rolling window at every roll: a row whose
    window would span a contract change is NaN until ``min_periods``
    observations have accumulated inside the new stretch.

    ``window`` accepts either form, and the choice matters once the grid
    frequency changes:

    - an **int** counts observations, so its duration is tied to the grid --
      ``120`` is two hours of a 1m grid but two minutes of a 1s grid;
    - a **time offset string** (``"2h"``, ``"30min"``) is a real duration and
      means the same thing at every frequency.

    Prefer the offset form for anything that should survive a change of grid.

    ``require_full_window`` keeps the convention honest: the statistic stays
    NaN until a whole window has accumulated inside the new stretch, so the
    warm-up after every roll is suppressed rather than being computed from a
    couple of observations. For an int window ``min_periods`` already does
    this; for an offset window ``min_periods`` is an observation count and
    cannot express the duration, so elapsed time is masked explicitly.
    """
    blocks = regime_blocks(regime)
    if min_periods is None and not isinstance(window, str):
        min_periods = window
    grouped = series.groupby(blocks, sort=False)
    rolled = getattr(grouped.rolling(window=window, min_periods=min_periods), stat)()
    out = rolled.reset_index(level=0, drop=True).reindex(series.index)

    if require_full_window and isinstance(window, str):
        stamps = pd.Series(series.index, index=series.index)
        elapsed = stamps - stamps.groupby(blocks).transform("first")
        out = out.where(elapsed >= pd.Timedelta(window))
    return out


def zscore_within_regime(
    series: pd.Series,
    regime: pd.Series,
    window: int | str = "2h",
    min_periods: int | None = None,
) -> pd.Series:
    """Rolling z-score computed inside a single contract pair.

    The z-score is what a roll damages most: an unhandled splice of 1-14
    spread sigma enters the numerator as a deviation the market never made.

    The window defaults to a duration rather than an observation count so the
    same call is meaningful on the 1s and 1m grids alike.
    """
    mean = rolling_within_regime(series, regime, window, min_periods, "mean")
    std = rolling_within_regime(series, regime, window, min_periods, "std")
    return (series - mean) / std


def build_aligned(grids: dict, freq: str) -> pd.DataFrame:
    """CL and BZ legs plus the front listed spread on one index."""
    cl = grids[("CL.v.0", freq)].add_prefix("cl_")
    bz = grids[("BZ.v.0", freq)].add_prefix("bz_")
    ls = grids[(FRONT_SPREAD, freq)].add_prefix("ls_")
    aligned = cl.join(bz, how="outer").join(ls, how="outer")

    aligned["synth_mid"] = aligned["cl_mid"] - aligned["bz_mid"]
    aligned["synth_bid"] = aligned["cl_bid_px_00"] - aligned["bz_ask_px_00"]
    aligned["synth_ask"] = aligned["cl_ask_px_00"] - aligned["bz_bid_px_00"]
    aligned["is_roll_date"] = aligned[["cl_is_roll_date", "bz_is_roll_date"]].any(axis=1)
    return aligned


def _grid_path(symbol: str, freq: str, start: str = PILOT_START, end: str = PILOT_END):
    return CLEAN_DIR / f"{_safe(symbol)}_{freq}_{start}_{end}.parquet"


def _events_path(symbol: str, start: str = PILOT_START, end: str = PILOT_END):
    return CLEAN_DIR / f"{_safe(symbol)}_events_{start}_{end}.parquet"


def _aligned_path(freq: str, start: str = PILOT_START, end: str = PILOT_END):
    return CLEAN_DIR / f"brent_wti_aligned_{freq}_{start}_{end}.parquet"


def load_grid(symbol: str, freq: str = "1s", **kw) -> pd.DataFrame:
    return pd.read_parquet(_grid_path(symbol, freq, **kw))


def load_spread_events(symbol: str = FRONT_SPREAD, **kw) -> pd.DataFrame:
    return pd.read_parquet(_events_path(symbol, **kw))


def load_aligned(freq: str = "1s", **kw) -> pd.DataFrame:
    return pd.read_parquet(_aligned_path(freq, **kw))


def main():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    grids = {}
    for symbol in OUTRIGHTS + SPREADS:
        events = clean_events(load_mbp1(symbol))
        print(f"{symbol}: {len(events):,} events, crossed: {events['is_crossed'].mean():.4%}")
        if symbol in SPREADS:
            events.to_parquet(_events_path(symbol))
        for freq in GRID_FREQS:
            grid = mark_roll_dates(to_grid(events, freq))
            grid.to_parquet(_grid_path(symbol, freq))
            grids[(symbol, freq)] = grid

    for freq in GRID_FREQS:
        aligned = build_aligned(grids, freq)
        aligned.to_parquet(_aligned_path(freq))
        n_quoted = aligned[["cl_mid", "bz_mid", "synth_mid"]].notna().all(axis=1).sum()
        print(
            f"aligned {freq}: {len(aligned):,} rows, "
            f"{n_quoted:,} with both legs quoted ({n_quoted / len(aligned):.1%})"
        )

    print(f"\nParquet files written to {CLEAN_DIR}")


if __name__ == "__main__":
    main()
