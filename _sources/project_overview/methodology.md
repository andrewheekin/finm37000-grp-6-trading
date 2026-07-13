# Methodology

## Approach

The strategy candidate is relative-value mean reversion on the Brent-WTI
spread. The current phase characterizes the spread empirically before any
trading rule is fixed: how wide deviations from trailing means get, how they
decay (PACF), when the books are liquid, and what crossing the spread costs
on each venue.

Two representations of the spread are carried side by side:

- **Synthetic spread** — constructed from the CL and BZ outright books:
  `synth_mid = cl_mid - bz_mid`, with the tradeable prices
  `synth_bid = cl_bid - bz_ask` (sell) and `synth_ask = cl_ask - bz_bid`
  (buy), i.e. each side crosses both leg books.
- **Listed spread** — the exchange-listed spread instruments' own books
  (`ls_*` columns), quoted as a single instrument.

## Cleaning and Alignment Conventions

- **Gridding:** last top-of-book quote per bucket at 1-second and 1-minute
  frequencies, per instrument.
- **Bounded forward-fill:** quotes carry forward for at most 600 seconds;
  beyond that (e.g. the daily maintenance break) buckets stay `NaN` rather
  than carrying a stale quote.
- **Carry-forward marker:** activity columns (`n_events`, `n_trades`,
  `volume`) are per-bucket facts and never filled, so `n_events == 0`
  identifies any bucket whose quote is a carry-forward.
- **Crossed/locked books** are flagged (`is_crossed`), not dropped —
  downstream code decides what to exclude.
- **Alignment:** legs are combined with an outer join on the UTC index, so
  no timestamps are silently discarded.
- **Rolls:** every row keeps its underlying `instrument_id`;
  `is_roll_date` flags dates whose mapped contract changed. The pilot week
  contains no rolls, so the flag is exercised by the full pull.

## Implementation Notes

- Pipeline steps are chained with `doit`:
  `pull_databento -> clean_mbp1 -> spread_diagnostics -> run_notebooks`.
  `doit clean` never deletes the billable DBN cache.
- Pure-function tests (`src/test_pipeline.py`, no network or API key) cover
  cache naming, event cleaning, gridding and the forward-fill limit, roll
  flagging, alignment, spread filtering, and the rolling-deviation
  transform.
- Comparative claims (venue choice, signal horizon, roll rule) are framed as
  measurements, not judgments; decisions are recorded in GitHub issues with
  the numbers that drove them.

## Caveats

- The pilot week is one mid-cycle week; estimates from it (liquidity
  profiles, deviation distributions) are conditional on that window.
- Roll handling is unit-tested but not yet exercised on real data.
