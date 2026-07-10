"""Pull MBP-1 market data for the Brent-WTI spread from Databento (issue #4).

Instruments:
- CL and BZ continuous front months, volume-based roll (.v.0 -- see issue #20
  for the .n.0 -> .v.0 decision and measurements).
- The exchange-listed same-month Brent-WTI spread instruments (CLxY-BZxY),
  which trade as single instruments with their own book.

Raw DBN files are cached one-per-symbol under DATA_DIR/databento; a pull is
skipped when its cache file already exists, so re-running is free. The
``load_`` functions read from that cache without touching the network.

Usage:
    python src/pull_databento.py          # pulls the pilot week

Requires DATABENTO_API_KEY in .env.
"""

from pathlib import Path

import databento as db
import pandas as pd

from settings import config

DATA_DIR = config("DATA_DIR")
DATABENTO_CACHE = DATA_DIR / "databento"

DATASET = "GLBX.MDP3"
SCHEMA = "mbp-1"

# Pilot week (Mon-Fri, mid-cycle for both legs under .v.0); end exclusive.
PILOT_START = "2026-06-01"
PILOT_END = "2026-06-06"

# stype_in="continuous" for the rolled outrights, "raw_symbol" for spreads.
OUTRIGHTS = ["CL.v.0", "BZ.v.0"]
SPREADS = ["CLQ6-BZQ6", "CLU6-BZU6"]


def _cache_path(symbol: str, schema: str, start: str, end: str) -> Path:
    """Cache filename for one symbol/schema/date-range pull.

    >>> _cache_path("CL.v.0", "mbp-1", "2026-06-01", "2026-06-06").name
    'glbx-mdp3_cl-v-0_mbp-1_2026-06-01_2026-06-06.dbn'
    """
    safe_dataset = DATASET.replace(".", "-").lower()
    safe_symbol = symbol.replace(".", "-").replace(":", "-").lower()
    return DATABENTO_CACHE / f"{safe_dataset}_{safe_symbol}_{schema}_{start}_{end}.dbn"


def pull_mbp1(
    symbol: str,
    stype_in: str,
    start: str = PILOT_START,
    end: str = PILOT_END,
    client: db.Historical | None = None,
) -> Path:
    """Download one symbol's MBP-1 range to the DBN cache; skip if cached."""
    path = _cache_path(symbol, SCHEMA, start, end)
    if path.exists():
        print(f"cached   {symbol}: {path.name}")
        return path
    DATABENTO_CACHE.mkdir(parents=True, exist_ok=True)
    if client is None:
        client = db.Historical(config("DATABENTO_API_KEY"))
    print(f"pulling  {symbol} ({start} to {end}) ...")
    data = client.timeseries.get_range(
        dataset=DATASET,
        symbols=[symbol],
        stype_in=stype_in,
        schema=SCHEMA,
        start=start,
        end=end,
    )
    data.to_file(path)
    print(f"saved    {symbol}: {path.name} ({path.stat().st_size / 1e6:.1f} MB)")
    return path


def load_mbp1(symbol: str, start: str = PILOT_START, end: str = PILOT_END) -> pd.DataFrame:
    """Load one symbol's cached MBP-1 pull as a DataFrame."""
    path = _cache_path(symbol, SCHEMA, start, end)
    if not path.exists():
        raise FileNotFoundError(
            f"No cached pull for {symbol} {start}..{end}; run pull_databento.py first."
        )
    return db.DBNStore.from_file(path).to_df()


def pull_all(start: str = PILOT_START, end: str = PILOT_END) -> list[Path]:
    client = db.Historical(config("DATABENTO_API_KEY"))
    paths = []
    for symbol in OUTRIGHTS:
        paths.append(pull_mbp1(symbol, "continuous", start, end, client))
    for symbol in SPREADS:
        paths.append(pull_mbp1(symbol, "raw_symbol", start, end, client))
    return paths


if __name__ == "__main__":
    paths = pull_all()
    total_mb = sum(p.stat().st_size for p in paths) / 1e6
    print(f"\n{len(paths)} files in cache, {total_mb:.1f} MB total")
    print(f"cache dir: {DATABENTO_CACHE}")
