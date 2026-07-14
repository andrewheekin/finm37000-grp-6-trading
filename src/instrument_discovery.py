"""Step 0 of the market-data pipeline (issue #4): instrument discovery.

Answers three questions from Databento metadata and one day of instrument
definitions -- no market-data pull required:

1. Do exchange-listed spread instruments with CL and BZ legs exist on CME
   Globex, and what are their exact symbols and instrument IDs?
2. When do the calendar (.c.0) and open-interest (.n.0) continuous-contract
   rules roll for CL and BZ? (feeds issue #20)
3. What would the pilot-week MBP-1 pull cost, in dollars and bytes?

Usage:
    python src/instrument_discovery.py

Requires DATABENTO_API_KEY in .env. Writes CSV artifacts to OUTPUT_DIR.
"""

import databento as db
import pandas as pd

from settings import config

DATASET = "GLBX.MDP3"
LEGS = ["CL", "BZ"]

# One recent full trading day is enough for a definition snapshot.
DEFINITION_DAY = "2026-06-01"
DEFINITION_DAY_END = "2026-06-02"

# Window over which to compare roll rules (~18 months, ~18 rolls per leg).
ROLL_WINDOW_START = "2025-01-01"
ROLL_WINDOW_END = "2026-07-01"

# Proposed pilot week (Mon-Fri, mid-cycle); end date exclusive.
PILOT_START = "2026-06-01"
PILOT_END = "2026-06-06"

OUTPUT_DIR = config("OUTPUT_DIR")


def get_client() -> db.Historical:
    return db.Historical(config("DATABENTO_API_KEY"))


def pull_definitions(client: db.Historical) -> pd.DataFrame:
    """Pull one day of instrument definitions for everything under the CL
    and BZ parent symbols (outrights, calendar spreads, and any spread
    instrument the exchange files under either product)."""
    data = client.timeseries.get_range(
        dataset=DATASET,
        symbols=[f"{leg}.FUT" for leg in LEGS],
        stype_in="parent",
        schema="definition",
        start=DEFINITION_DAY,
        end=DEFINITION_DAY_END,
    )
    return data.to_df()


def find_cl_bz_spreads(definitions: pd.DataFrame) -> pd.DataFrame:
    """Filter definition records to spread instruments referencing both legs.

    Multi-leg instruments are identified by instrument_class (not 'F'/'C'/'P')
    or by a positive leg_count where the column exists. An instrument
    referencing both CL and BZ is detected from its raw symbol, which on
    Globex contains both leg symbols (e.g. 'CLN6-BZN6' style).
    """
    df = definitions.copy()
    if "leg_count" in df.columns:
        multi_leg = df["leg_count"].fillna(0) > 0
    else:
        multi_leg = ~df["instrument_class"].isin(["F", "C", "P"])
    spreads = df[multi_leg]
    has_both = spreads["raw_symbol"].str.contains("CL") & spreads[
        "raw_symbol"
    ].str.contains("BZ")
    return spreads[has_both]


def resolve_roll_dates(client: db.Historical) -> pd.DataFrame:
    """Resolve each continuous rule to raw contracts over the roll window.

    Returns one row per (continuous symbol, interval): the raw contract and
    the dates it was the mapped front month. Roll dates are the interval
    start dates after the first.
    """
    continuous = [f"{leg}.{rule}.0" for leg in LEGS for rule in ("c", "n", "v")]
    # GLBX symbology does not support continuous -> raw_symbol directly, so
    # resolve continuous -> instrument_id, then instrument_id -> raw_symbol.
    to_ids = client.symbology.resolve(
        dataset=DATASET,
        symbols=continuous,
        stype_in="continuous",
        stype_out="instrument_id",
        start_date=ROLL_WINDOW_START,
        end_date=ROLL_WINDOW_END,
    )
    rows = []
    for cont_symbol, intervals in to_ids["result"].items():
        for iv in intervals:
            rows.append(
                {
                    "continuous": cont_symbol,
                    "instrument_id": iv["s"],
                    "from": iv["d0"],
                    "until": iv["d1"],
                }
            )
    df = pd.DataFrame(rows)

    ids = sorted(df["instrument_id"].unique())
    to_raw = client.symbology.resolve(
        dataset=DATASET,
        symbols=ids,
        stype_in="instrument_id",
        stype_out="raw_symbol",
        start_date=ROLL_WINDOW_START,
        end_date=ROLL_WINDOW_END,
    )
    id_to_symbol = {
        iid: intervals[0]["s"]
        for iid, intervals in to_raw["result"].items()
        if intervals
    }
    df["contract"] = df["instrument_id"].map(id_to_symbol)
    return df[["continuous", "contract", "instrument_id", "from", "until"]].sort_values(
        ["continuous", "from"]
    )


def pilot_cost(client: db.Historical, symbols: list, stype_in: str) -> dict:
    common = dict(
        dataset=DATASET,
        symbols=symbols,
        stype_in=stype_in,
        schema="mbp-1",
        start=PILOT_START,
        end=PILOT_END,
    )
    return {
        "symbols": ", ".join(symbols),
        "cost_usd": client.metadata.get_cost(**common),
        "billable_gb": client.metadata.get_billable_size(**common) / 1e9,
    }


def main():
    client = get_client()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)

    print("=" * 70)
    print(f"1. Spread instruments with CL and BZ legs ({DEFINITION_DAY})")
    print("=" * 70)
    definitions = pull_definitions(client)
    spreads = find_cl_bz_spreads(definitions)
    keep = [
        c
        for c in [
            "raw_symbol",
            "instrument_id",
            "instrument_class",
            "security_type",
            "asset",
            "leg_count",
            "leg_index",
            "leg_raw_symbol",
            "leg_side",
            "expiration",
        ]
        if c in spreads.columns
    ]
    if spreads.empty:
        print("No spread instruments referencing both CL and BZ were found")
        print("under the CL.FUT / BZ.FUT parents on this day.")
        cls_seen = definitions["instrument_class"].value_counts()
        print(f"\nInstrument classes present in the scan:\n{cls_seen}")
    else:
        # Same-month outright-vs-outright spreads (CLU6-BZU6 style) are the
        # tradeable Brent-WTI spread; everything else (differing months,
        # CL:BZ calendar combinations) is noise for our purposes.
        same_month = spreads[
            spreads["raw_symbol"].str.match(r"^CL([FGHJKMNQUVXZ]\d)-BZ\1$")
        ].sort_values("expiration")
        print(f"Total CL/BZ spread instruments: {len(spreads)}")
        print(f"Same-month outright spreads (CLxY-BZxY): {len(same_month)}")
        print("\nNearest 8 same-month spreads:")
        print(same_month[keep].head(8).to_string(index=False))
    spreads[keep].to_csv(OUTPUT_DIR / "cl_bz_spread_instruments.csv", index=False)
    definitions.to_csv(OUTPUT_DIR / "cl_bz_definitions_snapshot.csv", index=False)
    print(f"\nDefinition records scanned: {len(definitions)}")

    print()
    print("=" * 70)
    print(f"2. Roll dates, .c.0 vs .n.0 ({ROLL_WINDOW_START} to {ROLL_WINDOW_END})")
    print("=" * 70)
    rolls = resolve_roll_dates(client)
    rolls.to_csv(OUTPUT_DIR / "roll_dates_c_vs_n.csv", index=False)
    for cont_symbol, group in rolls.groupby("continuous"):
        print(f"\n{cont_symbol}:")
        print(group[["contract", "from", "until"]].to_string(index=False))

    print()
    print("=" * 70)
    print(f"3. Pilot-week MBP-1 cost ({PILOT_START} to {PILOT_END})")
    print("=" * 70)
    outright_cost = pilot_cost(
        client, [f"{leg}.n.0" for leg in LEGS], stype_in="continuous"
    )
    print(
        f"Outrights ({outright_cost['symbols']}): "
        f"${outright_cost['cost_usd']:.2f}, {outright_cost['billable_gb']:.3f} GB"
    )
    if not spreads.empty:
        # Front two same-month spreads: the instruments we would actually use.
        spread_symbols = (
            spreads[spreads["raw_symbol"].str.match(r"^CL([FGHJKMNQUVXZ]\d)-BZ\1$")]
            .sort_values("expiration")["raw_symbol"]
            .head(2)
            .tolist()
        )
        spread_cost = pilot_cost(client, spread_symbols, stype_in="raw_symbol")
        print(
            f"Spreads ({spread_cost['symbols']}): "
            f"${spread_cost['cost_usd']:.2f}, {spread_cost['billable_gb']:.3f} GB"
        )

    print(f"\nArtifacts written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
