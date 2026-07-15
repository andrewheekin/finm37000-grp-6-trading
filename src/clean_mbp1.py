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
differs from the previous date's. The pilot week contains no rolls, so the
flag is exercised by the full pull.

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
