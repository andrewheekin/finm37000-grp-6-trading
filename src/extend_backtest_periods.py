"""Download and clean additional execution-ready weeks for the backtest.

The production pilot pipeline hard-codes its 2026 listed spread. This helper
resolves the CL.v.0 and BZ.v.0 contracts for each requested historical week,
downloads only those two continuous outrights and their matching exchange-
listed CL-BZ spread, and writes a strategy-ready aligned 1-minute parquet.

Usage:
    python src/extend_backtest_periods.py --estimate-only
    python src/extend_backtest_periods.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import databento as db
import pandas as pd

from clean_mbp1 import CLEAN_DIR, clean_events, mark_roll_dates, to_grid
from pull_databento import DATASET, DATABENTO_CACHE
from settings import config


@dataclass(frozen=True)
class Period:
    start: str
    end: str
    spread: str


PERIODS = [
    # Three consecutive blocks per year, matching the existing 2023/2026
    # backtest layout. The third block uses the post-roll listed spread.
    Period("2024-05-01", "2024-05-06", "CLM4-BZN4"),
    Period("2024-05-06", "2024-05-13", "CLM4-BZN4"),
    Period("2024-05-13", "2024-05-20", "CLN4-BZQ4"),
    Period("2025-04-28", "2025-05-05", "CLM5-BZN5"),
    Period("2025-05-01", "2025-05-06", "CLM5-BZN5"),
    Period("2025-05-06", "2025-05-13", "CLM5-BZN5"),
    Period("2025-05-13", "2025-05-20", "CLN5-BZQ5"),
    # Two appended weeks per annual backtest window.
    Period("2023-05-20", "2023-05-27", "CLN3-BZQ3"),
    Period("2023-05-27", "2023-06-03", "CLN3-BZQ3"),
    Period("2024-05-20", "2024-05-27", "CLN4-BZQ4"),
    Period("2024-05-27", "2024-06-03", "CLN4-BZQ4"),
    Period("2025-05-20", "2025-05-27", "CLN5-BZQ5"),
    Period("2025-05-27", "2025-06-03", "CLN5-BZQ5"),
    Period("2026-06-20", "2026-06-27", "CLQ6-BZQ6"),
    Period("2026-06-27", "2026-07-04", "CLQ6-BZU6"),
]

OUTRIGHTS = ("CL.v.0", "BZ.v.0")
BBO_SCHEMA = "bbo-1m"


def _safe(symbol: str) -> str:
    return symbol.replace(".", "-").replace(":", "-").lower()


def bbo_path(symbol: str, period: Period):
    return DATABENTO_CACHE / (
        f"glbx-mdp3_{_safe(symbol)}_{BBO_SCHEMA}_{period.start}_{period.end}.dbn"
    )


def pull_bbo(client: db.Historical, symbol: str, stype_in: str, period: Period):
    path = bbo_path(symbol, period)
    if path.exists():
        print(f"cached   {symbol}: {path.name}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"pulling  {symbol} ({period.start} to {period.end}) ...")
    data = client.timeseries.get_range(
        dataset=DATASET,
        symbols=[symbol],
        stype_in=stype_in,
        schema=BBO_SCHEMA,
        start=period.start,
        end=period.end,
    )
    data.to_file(path)
    print(f"saved    {symbol}: {path.name} ({path.stat().st_size / 1e6:.1f} MB)")
    return path


def load_bbo(symbol: str, period: Period) -> pd.DataFrame:
    frame = db.DBNStore.from_file(bbo_path(symbol, period)).to_df()
    # Reuse the project's grid builder. BBO-1m has one quote observation per
    # minute but no MBP action flag, so mark every observation non-trade.
    frame["action"] = "N"
    return frame


def estimate_period(
    client: db.Historical, period: Period
) -> tuple[float, float]:
    requests = [
        dict(symbols=list(OUTRIGHTS), stype_in="continuous"),
        dict(symbols=[period.spread], stype_in="raw_symbol"),
    ]
    total_cost = 0.0
    total_bytes = 0
    for request in requests:
        common = dict(
            dataset=DATASET,
            schema=BBO_SCHEMA,
            start=period.start,
            end=period.end,
            **request,
        )
        total_cost += client.metadata.get_cost(**common)
        total_bytes += client.metadata.get_billable_size(**common)
    return total_cost, total_bytes / 1e9


def aligned_path(period: Period):
    return CLEAN_DIR / f"brent_wti_aligned_1m_{period.start}_{period.end}.parquet"


def clean_period(period: Period) -> pd.DataFrame:
    grids = {}
    for symbol in (*OUTRIGHTS, period.spread):
        events = clean_events(load_bbo(symbol, period))
        grids[symbol] = mark_roll_dates(to_grid(events, "1m"))

    aligned = (
        grids["CL.v.0"].add_prefix("cl_")
        .join(grids["BZ.v.0"].add_prefix("bz_"), how="outer")
        .join(grids[period.spread].add_prefix("ls_"), how="outer")
    )
    aligned["synth_mid"] = aligned["cl_mid"] - aligned["bz_mid"]
    aligned["synth_bid"] = aligned["cl_bid_px_00"] - aligned["bz_ask_px_00"]
    aligned["synth_ask"] = aligned["cl_ask_px_00"] - aligned["bz_bid_px_00"]
    aligned["is_roll_date"] = aligned[["cl_is_roll_date", "bz_is_roll_date"]].any(axis=1)

    path = aligned_path(period)
    path.parent.mkdir(parents=True, exist_ok=True)
    aligned.to_parquet(path)
    return aligned


def main(estimate_only: bool = False, skip_estimate: bool = False):
    client = db.Historical(config("DATABENTO_API_KEY"))
    resolved = list(PERIODS)
    total_cost = 0.0
    total_gb = 0.0

    if not skip_estimate:
        for period in PERIODS:
            cost, billable_gb = estimate_period(client, period)
            total_cost += cost
            total_gb += billable_gb
            print(
                f"{period.start}..{period.end}: {period.spread}, "
                f"estimated ${cost:.2f}, {billable_gb:.3f} GB"
            )
        print(f"total estimate: ${total_cost:.2f}, {total_gb:.3f} GB")
    if estimate_only:
        return

    for period in resolved:
        if aligned_path(period).exists():
            print(f"cached aligned: {aligned_path(period)}")
            continue
        pull_bbo(client, "CL.v.0", "continuous", period)
        pull_bbo(client, "BZ.v.0", "continuous", period)
        pull_bbo(client, period.spread, "raw_symbol", period)
        aligned = clean_period(period)
        print(
            f"saved {aligned_path(period)}: {len(aligned):,} rows, "
            f"{aligned['synth_mid'].notna().sum():,} quoted spreads"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument("--skip-estimate", action="store_true")
    args = parser.parse_args()
    main(estimate_only=args.estimate_only, skip_estimate=args.skip_estimate)
