"""Roll diagnostics for the Brent-WTI continuous series (issue #20).

The strategy is intraday and flat at EOD, so no position is held through a
roll. The problem is statistical: a continuous series splices two contracts,
so any rolling window spanning a roll mixes them, and the splice injects the
calendar-spread price as a spurious return.

This script measures that contamination in two tiers.

**Tier 1 -- jump distribution (``ohlcv-1d``, full sample).** On the session
before a roll, the outgoing and incoming contracts both trade, so the
discontinuity is measurable exactly:

    jump = close(incoming, prior_session) - close(outgoing, prior_session)

The continuous series' return on the roll date equals the incoming contract's
true return *plus* this jump, so ``jump`` is precisely the contamination. Run
over every ``.v.0`` roll in the sample this gives ~18 observations per leg,
which is what sizing the fix requires -- one roll week gives one.

**Tier 2 -- intraday mechanics (``mbp-1``, one roll window).** June 2026
contains a staggered pair: CL rolls 2026-06-18 (CLN6 -> CLQ6), BZ rolls
2026-06-28 (BZQ6 -> BZU6). That exercises the case where one leg rolls and
the other does not, which is the case the pilot week could not reach. Pulled
and cleaned through the same ``clean_mbp1`` code as the pilot so that
``is_roll_date`` is exercised on real rolls.

**Tier 3 -- what the convention costs.** How much of the sample is lost by
refusing to let a rolling window span a contract change, which is the price of
the convention adopted in ``data_manual/data_README.md`` and implemented by
``clean_mbp1.regime_key`` / ``rolling_within_regime``.

Usage:
    python src/roll_analysis.py           # tiers 1 and 3 (daily bars only)
    python src/roll_analysis.py --mbp1    # adds tier 2 (intraday pull)

Requires DATABENTO_API_KEY in .env, and the roll table written by
``python src/instrument_discovery.py``. Writes CSVs to OUTPUT_DIR.
"""

import argparse
from pathlib import Path

import databento as db
import pandas as pd

from pull_databento import DATABENTO_CACHE, DATASET, _cache_path
from settings import config

OUTPUT_DIR = config("OUTPUT_DIR")

LEGS = ["CL", "BZ"]
ROLL_RULE = "v"  # volume-based; see issue #20 for the .n.0 -> .v.0 decision

# Same window instrument_discovery.py used to build the roll table.
SAMPLE_START = "2025-01-01"
SAMPLE_END = "2026-07-01"

ROLL_TABLE = OUTPUT_DIR / "roll_dates_c_vs_n.csv"

# An interval shorter than this is a flip-back (the .v.0 rule bouncing
# between two contracts whose volumes are close), not a genuine roll.
WHIPSAW_MAX_DAYS = 5

# Tier 2: staggered-roll window. CL rolls 2026-06-18, BZ rolls 2026-06-28.
ROLL_WINDOW_START = "2026-06-15"
ROLL_WINDOW_END = "2026-07-01"
ROLL_WINDOW_OUTRIGHTS = ["CLN6", "CLQ6", "BZQ6", "BZU6"]
ROLL_WINDOW_CONTINUOUS = [f"{leg}.{ROLL_RULE}.0" for leg in LEGS]

# The intraday shape of the splice is a price-level effect, so ohlcv-1m covers
# the whole window cheaply. MBP-1 is pulled only across the CL roll, which is
# enough to exercise the real clean_mbp1 path on book data -- the pilot week is
# ~43 MB/day/leg at mbp-1, so the full window would be ~1 GB for no extra
# information about the flag.
MBP1_WINDOW_START = "2026-06-17"
MBP1_WINDOW_END = "2026-06-20"
CL_ROLL_DATE = pd.Timestamp("2026-06-18")


def get_client() -> db.Historical:
    return db.Historical(config("DATABENTO_API_KEY"))


# ---------------------------------------------------------------- pulling


def pull(
    symbols: list[str],
    stype_in: str,
    schema: str,
    start: str,
    end: str,
    client: db.Historical | None = None,
) -> Path:
    """Download one multi-symbol range to the DBN cache; skip if cached.

    Mirrors ``pull_databento.pull_mbp1`` but takes a symbol *list* and an
    explicit schema, so several contracts share one cache file.
    """
    tag = symbols[0] if len(symbols) == 1 else f"{symbols[0]}+{len(symbols) - 1}"
    path = _cache_path(tag, schema, start, end)
    if path.exists():
        print(f"cached   {tag} [{schema}]: {path.name}")
        return path
    DATABENTO_CACHE.mkdir(parents=True, exist_ok=True)
    if client is None:
        client = get_client()
    print(f"pulling  {len(symbols)} symbol(s) [{schema}] {start}..{end} ...")
    data = client.timeseries.get_range(
        dataset=DATASET,
        symbols=symbols,
        stype_in=stype_in,
        schema=schema,
        start=start,
        end=end,
    )
    data.to_file(path)
    print(f"saved    {tag} [{schema}]: {path.name} ({path.stat().st_size / 1e6:.1f} MB)")
    return path


def load(symbols: list[str], schema: str, start: str, end: str) -> pd.DataFrame:
    """Load a cached multi-symbol pull as a DataFrame."""
    tag = symbols[0] if len(symbols) == 1 else f"{symbols[0]}+{len(symbols) - 1}"
    path = _cache_path(tag, schema, start, end)
    if not path.exists():
        raise FileNotFoundError(f"No cached pull at {path}; run roll_analysis.py first.")
    return db.DBNStore.from_file(path).to_df()


# ------------------------------------------------------------ roll table


def load_roll_schedule(rule: str = ROLL_RULE) -> pd.DataFrame:
    """Read the continuous-symbology intervals for one roll rule.

    Returns one row per (leg, interval) with ``from``/``until`` as dates,
    sorted within leg.
    """
    if not ROLL_TABLE.exists():
        raise FileNotFoundError(
            f"{ROLL_TABLE} not found; run `python src/instrument_discovery.py` first."
        )
    df = pd.read_csv(ROLL_TABLE, parse_dates=["from", "until"])
    df = df[df["continuous"].str.endswith(f".{rule}.0")].copy()
    df["leg"] = df["continuous"].str.split(".").str[0]
    return df.sort_values(["leg", "from"]).reset_index(drop=True)


def roll_events(schedule: pd.DataFrame) -> pd.DataFrame:
    """Consecutive intervals -> one row per roll event.

    ``is_whipsaw`` marks an event whose *outgoing* contract was held for
    fewer than WHIPSAW_MAX_DAYS days, i.e. the rule bouncing between two
    contracts rather than migrating once.
    """
    rows = []
    for leg, group in schedule.groupby("leg"):
        group = group.sort_values("from").reset_index(drop=True)
        for i in range(1, len(group)):
            prev, cur = group.iloc[i - 1], group.iloc[i]
            held_days = (prev["until"] - prev["from"]).days
            rows.append(
                {
                    "leg": leg,
                    "roll_date": cur["from"],
                    "outgoing": prev["contract"],
                    "incoming": cur["contract"],
                    "outgoing_held_days": held_days,
                    "is_whipsaw": held_days < WHIPSAW_MAX_DAYS,
                }
            )
    return pd.DataFrame(rows).sort_values(["leg", "roll_date"]).reset_index(drop=True)


# ------------------------------------------------------- tier 1: jumps


def daily_bars(schedule: pd.DataFrame, client: db.Historical) -> dict[str, pd.DataFrame]:
    """Daily closes and volumes for every contract the .v.0 rule touched.

    Returns ``{"close": wide, "volume": wide}``, each indexed by session date
    with raw contract symbols as columns. Volume is carried so that a jump
    measured against a thinly-traded outgoing contract can be spotted rather
    than assumed away.
    """
    frames = {"close": [], "volume": []}
    for _leg, group in schedule.groupby("leg"):
        contracts = sorted(group["contract"].dropna().unique())
        pull(contracts, "raw_symbol", "ohlcv-1d", SAMPLE_START, SAMPLE_END, client)
        df = load(contracts, "ohlcv-1d", SAMPLE_START, SAMPLE_END)
        if "symbol" not in df.columns:
            id_to_sym = dict(zip(group["instrument_id"], group["contract"]))
            df["symbol"] = df["instrument_id"].map(id_to_sym)
        df = df.reset_index()
        ts_col = "ts_event" if "ts_event" in df.columns else df.columns[0]
        df["date"] = pd.to_datetime(df[ts_col]).dt.tz_localize(None).dt.normalize()
        for field in frames:
            frames[field].append(
                df.pivot_table(index="date", columns="symbol", values=field)
            )
    return {f: pd.concat(v, axis=1).sort_index() for f, v in frames.items()}


def measure_jumps(events: pd.DataFrame, bars: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Attach the measured splice jump to each roll event.

    The jump is taken on the last session strictly before the roll date on
    which *both* contracts have a close, so the two prices are contemporaneous
    and any overnight market move is common to them and cancels. Both legs'
    volumes on that session are recorded alongside it.
    """
    closes, volumes = bars["close"], bars["volume"]
    out = events.copy()
    jumps, ref_dates, vol_out, vol_in = [], [], [], []
    for _, ev in out.iterrows():
        cols = [ev["outgoing"], ev["incoming"]]
        pair = (
            closes.loc[closes.index < ev["roll_date"], cols].dropna()
            if set(cols).issubset(closes.columns)
            else pd.DataFrame()
        )
        if pair.empty:
            jumps.append(pd.NA)
            ref_dates.append(pd.NaT)
            vol_out.append(pd.NA)
            vol_in.append(pd.NA)
            continue
        ref = pair.index[-1]
        last = pair.iloc[-1]
        jumps.append(last[ev["incoming"]] - last[ev["outgoing"]])
        ref_dates.append(ref)
        vol_out.append(volumes.at[ref, ev["outgoing"]] if ref in volumes.index else pd.NA)
        vol_in.append(volumes.at[ref, ev["incoming"]] if ref in volumes.index else pd.NA)
    out["ref_session"] = ref_dates
    out["jump"] = pd.to_numeric(pd.Series(jumps), errors="coerce")
    out["vol_outgoing"] = pd.to_numeric(pd.Series(vol_out), errors="coerce")
    out["vol_incoming"] = pd.to_numeric(pd.Series(vol_in), errors="coerce")
    return out


def front_series(schedule: pd.DataFrame, closes: pd.DataFrame) -> pd.DataFrame:
    """Continuous front-month close and held contract per leg, per session."""
    cols = {}
    for leg, group in schedule.groupby("leg"):
        px = pd.Series(index=closes.index, dtype=float)
        held = pd.Series(index=closes.index, dtype=object)
        for _, iv in group.iterrows():
            if iv["contract"] not in closes.columns:
                continue
            mask = (closes.index >= iv["from"]) & (closes.index < iv["until"])
            px[mask] = closes.loc[mask, iv["contract"]]
            held[mask] = iv["contract"]
        cols[f"{leg}_px"] = px
        cols[f"{leg}_contract"] = held
    return pd.DataFrame(cols)


def clean_spread_sigma(front: pd.DataFrame) -> tuple[float, float, pd.Series]:
    """Daily sigma of the CL-BZ spread with roll-contaminated diffs removed.

    A day-over-day spread change is usable only when *both* legs held the same
    contract on both days; otherwise the change contains a splice jump. Using
    the raw continuous series here would normalise the contamination by a sigma
    the contamination itself inflates, so those diffs are dropped.
    """
    spread = (front["CL_px"] - front["BZ_px"]).dropna()
    same_contract = (
        front["CL_contract"].eq(front["CL_contract"].shift())
        & front["BZ_contract"].eq(front["BZ_contract"].shift())
    ).reindex(spread.index, fill_value=False)
    clean_diffs = spread.diff()[same_contract].dropna()
    return spread.mean(), clean_diffs.std(), clean_diffs


def spread_jump_impact(
    jumps: pd.DataFrame, schedule: pd.DataFrame, closes: pd.DataFrame
) -> pd.DataFrame:
    """Per-roll jump expressed against the spread's roll-free daily volatility.

    The traded spread is CL - BZ, so a roll in either leg moves the spread by
    that leg's jump (sign +1 for CL, -1 for BZ). Scaling by a roll-free sigma
    says how large the splice is relative to the spread's genuine day-to-day
    variation -- the quantity that decides whether a window spanning a roll is
    usable.
    """
    front = front_series(schedule, closes)
    mean, sigma, clean_diffs = clean_spread_sigma(front)

    out = jumps.copy()
    out["spread_impact"] = out["jump"] * out["leg"].map({"CL": 1.0, "BZ": -1.0})
    out["impact_in_sigma"] = out["spread_impact"] / sigma
    out.attrs["spread_daily_sigma"] = sigma
    out.attrs["spread_mean"] = mean
    out.attrs["n_clean_diffs"] = len(clean_diffs)
    return out


def report_jumps(jumps: pd.DataFrame) -> None:
    sigma = jumps.attrs.get("spread_daily_sigma", float("nan"))
    print("=" * 72)
    print(f"Tier 1: splice jumps at every .{ROLL_RULE}.0 roll, {SAMPLE_START}..{SAMPLE_END}")
    print("=" * 72)
    print(
        f"\nCL-BZ spread: mean {jumps.attrs.get('spread_mean', float('nan')):.3f}, "
        f"roll-free daily sigma {sigma:.3f} "
        f"(from {jumps.attrs.get('n_clean_diffs', 0)} uncontaminated diffs)"
    )
    for leg, group in jumps.groupby("leg"):
        genuine = group[~group["is_whipsaw"]]["jump"].dropna()
        whip = group[group["is_whipsaw"]]["jump"].dropna()
        print(f"\n{leg}: {len(genuine)} genuine rolls, {len(whip)} flip-backs")
        if len(genuine):
            print(
                f"  jump  mean {genuine.mean():+.3f}  sd {genuine.std():.3f}  "
                f"min {genuine.min():+.3f}  max {genuine.max():+.3f}  "
                f"mean|jump| {genuine.abs().mean():.3f}"
            )
    impact = jumps["impact_in_sigma"].abs().dropna()
    if len(impact):
        print(
            f"\nSpread impact, all rolls: mean |jump| = {impact.mean():.2f} sigma, "
            f"max {impact.max():.2f} sigma"
        )

    # The term structure steepened sharply in 2026, so the pooled figure hides
    # how large the splice became in the recent regime. Split by calendar year.
    print("\nBy year (|jump| in spread sigma):")
    by_year = (
        jumps.assign(year=jumps["roll_date"].dt.year, abs_sig=impact)
        .dropna(subset=["abs_sig"])
        .groupby(["year", "leg"])["abs_sig"]
        .agg(["count", "mean", "max"])
    )
    print(by_year.to_string())

    print("\nPer-roll detail:")
    cols = [
        "leg",
        "roll_date",
        "outgoing",
        "incoming",
        "ref_session",
        "jump",
        "vol_outgoing",
        "vol_incoming",
        "impact_in_sigma",
        "is_whipsaw",
    ]
    show = jumps[cols].copy()
    show["roll_date"] = show["roll_date"].dt.date
    show["ref_session"] = show["ref_session"].dt.date
    print(show.to_string(index=False))


# ------------------------------------------- tier 2: intraday roll window


def pull_roll_window(client: db.Historical) -> None:
    """Data for the staggered June 2026 rolls.

    The outrights are pulled alongside the continuous series so the splice can
    be seen from both sides -- the continuous series shows the discontinuity,
    the two outrights show that each contract itself is continuous through it.
    """
    pull(ROLL_WINDOW_CONTINUOUS, "continuous", "ohlcv-1m",
         ROLL_WINDOW_START, ROLL_WINDOW_END, client)
    pull(ROLL_WINDOW_OUTRIGHTS, "raw_symbol", "ohlcv-1m",
         ROLL_WINDOW_START, ROLL_WINDOW_END, client)
    pull(ROLL_WINDOW_CONTINUOUS, "continuous", "mbp-1",
         MBP1_WINDOW_START, MBP1_WINDOW_END, client)


def _minute_frame(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    """ohlcv-1m closes, wide by symbol."""
    df = load(symbols, "ohlcv-1m", start, end).reset_index()
    ts_col = "ts_event" if "ts_event" in df.columns else df.columns[0]
    df["ts"] = pd.to_datetime(df[ts_col])
    return df.pivot_table(index="ts", columns="symbol", values="close").sort_index()


def report_splice(minutes_per_day: int = 3) -> pd.DataFrame:
    """Show the continuous series' discontinuity against the raw contracts.

    Prints the last minutes of the session before the CL roll and the first
    minutes after it, for the continuous series and both underlying contracts,
    so the splice is visible as a level shift in the former and absent in the
    latter two.
    """
    cont = _minute_frame(ROLL_WINDOW_CONTINUOUS, ROLL_WINDOW_START, ROLL_WINDOW_END)
    outr = _minute_frame(ROLL_WINDOW_OUTRIGHTS, ROLL_WINDOW_START, ROLL_WINDOW_END)
    joined = cont.join(outr, how="outer").sort_index()

    print()
    print("=" * 72)
    print(f"Tier 2a: the splice at the CL roll ({CL_ROLL_DATE.date()}, CLN6 -> CLQ6)")
    print("=" * 72)
    boundary = CL_ROLL_DATE.tz_localize(joined.index.tz)
    before = joined.loc[joined.index < boundary].tail(minutes_per_day)
    after = joined.loc[joined.index >= boundary].head(minutes_per_day)
    cols = [c for c in ["CL.v.0", "CLN6", "CLQ6", "BZ.v.0", "BZQ6"] if c in joined.columns]
    print("\nLast minutes before the roll boundary:")
    print(before[cols].to_string())
    print("\nFirst minutes after:")
    print(after[cols].to_string())

    # ohlcv bars only appear in minutes that traded, so take the last and first
    # *quoted* minute rather than the last and first row of the window.
    if "CL.v.0" in joined.columns:
        prior = joined.loc[joined.index < boundary, "CL.v.0"].dropna()
        post = joined.loc[joined.index >= boundary, "CL.v.0"].dropna()
        if len(prior) and len(post):
            print(
                f"\nCL.v.0 last quote before boundary {prior.iloc[-1]:.2f} "
                f"({prior.index[-1]}) -> first after {post.iloc[0]:.2f} "
                f"({post.index[0]}): {post.iloc[0] - prior.iloc[-1]:+.3f}"
            )
        if {"CLN6", "CLQ6"}.issubset(joined.columns):
            same = joined.loc[joined.index < boundary, ["CLN6", "CLQ6"]].dropna()
            if not same.empty:
                spot = same.iloc[-1]
                print(
                    f"Contemporaneous CLQ6 - CLN6 at {same.index[-1]}: "
                    f"{spot['CLQ6'] - spot['CLN6']:+.3f}  "
                    "(the splice the continuous series absorbs)"
                )
    return joined


def contamination_cost(schedule: pd.DataFrame, windows=(60, 120)) -> pd.DataFrame:
    """How much of the sample a rolling window spanning a roll contaminates.

    The legs roll on different dates, so the object that must stay constant
    within a window is the *pair* of held contracts. Each change of that pair
    -- either leg rolling, or a flip-back -- contaminates the next ``w``
    minutes of a ``w``-minute trailing window.
    """
    dates = pd.date_range(schedule["from"].min(), schedule["until"].max(), freq="B")
    held = {}
    for leg, group in schedule.groupby("leg"):
        s = pd.Series(index=dates, dtype=object)
        for _, iv in group.iterrows():
            s[(dates >= iv["from"]) & (dates < iv["until"])] = iv["contract"]
        held[leg] = s
    pair = held["CL"].astype(str) + "/" + held["BZ"].astype(str)
    changes = pair.ne(pair.shift()).sum() - 1  # first row is not a change

    # CME Globex trades ~23h/day; the maintenance break is the only gap.
    minutes_per_day = 23 * 60
    total_minutes = len(dates) * minutes_per_day
    rows = [
        {
            "window_min": w,
            "regime_changes": int(changes),
            "minutes_contaminated": int(changes) * w,
            "pct_of_sample": 100 * int(changes) * w / total_minutes,
        }
        for w in windows
    ]
    out = pd.DataFrame(rows)
    print()
    print("=" * 72)
    print("Tier 3: cost of excluding windows that span a contract change")
    print("=" * 72)
    print(
        f"\n{len(dates)} business days, contract-pair changes: {int(changes)} "
        f"(~1 per {len(dates) / max(1, changes):.0f} sessions)"
    )
    print(out.to_string(index=False))
    return out


def report_roll_window() -> pd.DataFrame:
    """Check is_roll_date fires correctly on real book data through a roll."""
    from clean_mbp1 import clean_events, mark_roll_dates, to_grid

    df = load(ROLL_WINDOW_CONTINUOUS, "mbp-1", MBP1_WINDOW_START, MBP1_WINDOW_END)
    print()
    print("=" * 72)
    print(f"Tier 2b: is_roll_date on mbp-1, {MBP1_WINDOW_START}..{MBP1_WINDOW_END}")
    print("=" * 72)

    rows = []
    for symbol in ROLL_WINDOW_CONTINUOUS:
        leg = symbol.split(".")[0]
        sub = df[df["symbol"] == symbol] if "symbol" in df.columns else df
        if sub.empty:
            print(f"\n{symbol}: no rows in pull")
            continue
        grid = mark_roll_dates(to_grid(clean_events(sub), "1m"))
        flagged = sorted({d for d in grid.index[grid["is_roll_date"]].date})
        by_date = grid.groupby(grid.index.date)["instrument_id"].agg(
            ["first", "last", "nunique"]
        )
        print(f"\n{symbol}: {len(grid):,} 1m buckets, flagged roll dates: {flagged}")
        print(by_date.to_string())
        for d, r in by_date.iterrows():
            rows.append(
                {
                    "leg": leg,
                    "date": d,
                    "first_id": r["first"],
                    "last_id": r["last"],
                    "n_ids": r["nunique"],
                    "is_roll_date": d in set(flagged),
                }
            )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main


def main(do_mbp1: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = get_client()

    schedule = load_roll_schedule()
    events = roll_events(schedule)
    bars = daily_bars(schedule, client)
    jumps = spread_jump_impact(measure_jumps(events, bars), schedule, bars["close"])
    report_jumps(jumps)

    cost = contamination_cost(schedule)

    jumps.to_csv(OUTPUT_DIR / "roll_jumps.csv", index=False)
    bars["close"].to_csv(OUTPUT_DIR / "roll_contract_closes.csv")
    cost.to_csv(OUTPUT_DIR / "roll_contamination_cost.csv", index=False)
    print(f"\nWrote {OUTPUT_DIR / 'roll_jumps.csv'}")

    if do_mbp1:
        pull_roll_window(client)
        report_splice()
        window = report_roll_window()
        window.to_csv(OUTPUT_DIR / "roll_window_flags.csv", index=False)
        print(f"\nWrote {OUTPUT_DIR / 'roll_window_flags.csv'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mbp1",
        action="store_true",
        help="also pull and check the intraday June 2026 roll window",
    )
    args = parser.parse_args()
    main(do_mbp1=args.mbp1)
