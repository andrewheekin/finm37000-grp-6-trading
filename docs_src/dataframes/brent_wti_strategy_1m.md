# Brent-WTI Strategy Backtest (1-minute)

## Description

Per-bar output of the final Brent–WTI mean-reversion backtest
(`src/strategy_engine.py`). One row per one-minute bar inside the 00:00–19:59
UTC session, carrying the rolling statistics the entry gates saw, the position
state, the exit that closed it, and executable P&L.

This is the artifact behind every number on the
[Strategy Results](../strategy_results.md) page: 6,000 bars over June 1–5,
2026, 4 trades, +\$330 cumulative P&L.

Signals come from the synthetic spread (`synth_mid = cl_mid − bz_mid`), but
P&L is marked against the **listed** `CLN6-BZQ6` spread's own book, so the
quoted bid–ask is paid on entry and exit rather than assuming mid-price fills.

Load it in analysis code with:

```python
import pandas as pd
from strategy_engine import results_path

results = pd.read_parquet(results_path())
```

Or re-run the backtest with different parameters, without touching the saved
parquet:

```python
from clean_mbp1 import load_aligned
from strategy_engine import run_strategy

results = run_strategy(
    data=load_aligned("1m"),
    window=30,
    deviation_threshold=2.5,
    halflife_threshold=15.0,
    exit_threshold=0.5,
    stop_loss=1000,
    time_stop=30,
)
```

Requires the local 1-minute aligned parquet (`doit clean_mbp1`) and
`doit run_strategy`.

## Conventions

- **No lookahead.** Rolling $\mu$ / $\sigma$ at time $t$ use the 30 bars ending
  at $t$, including $S_t$ itself, which is observed at decision time.
- **Sign convention.** `position = +1` is long the spread (entered at the
  listed ask, liquidated at the bid); `position = -1` is short (entered at the
  bid, covered at the ask).
- **One contract at a time.** While a position is open the entry gates are not
  evaluated, so a bar is either a candidate for entry or part of an open trade,
  never both.
- **Window validity.** A window is used only when it holds 30 consecutive
  one-minute bars from a single `(CL contract, BZ contract)` regime with live
  quotes on both legs. `rolling_mean`, `rolling_std`, and `zscore` are `NaN`
  otherwise — 175 of 6,000 bars in the pilot week.
- **P&L units.** All P&L columns are USD, using a 1,000-barrel contract
  multiplier against a spread quoted in $/bbl.
- **Exit precedence.** Mean reversion, then stop loss, then time stop, then
  session end. `exit_flag` and the entry flags are never `True` on the same row.

## Data Dictionary

Index: `ts_recv` — `datetime64[ns, UTC]`, 1-minute buckets, restricted to
00:00–19:59 UTC (same buckets as the aligned source).

Market data:

- **`synth_mid`**: `float64` — synthetic spread mid (`cl_mid − bz_mid`), the series the signal is computed on
- **`ls_bid`**: `float64` — best bid of the listed `CLN6-BZQ6` spread, used to open shorts and close longs
- **`ls_ask`**: `float64` — best ask of the listed spread, used to open longs and close shorts

Entry-gate state:

- **`rolling_mean`**: `float64` — trailing 30-bar mean of `synth_mid` through the current bar; `NaN` when the window is invalid
- **`rolling_std`**: `float64` — trailing 30-bar sample standard deviation (`ddof=1`)
- **`zscore`**: `float64` — `(synth_mid - rolling_mean) / rolling_std`
- **`halflife`**: `float64` — AR(1) half-life in minutes, populated only on bars where the half-life gate ran, then carried for the life of the resulting position; `NaN` otherwise
- **`long_entry`**: `bool` — `True` on the bar a long spread position is opened
- **`short_entry`**: `bool` — `True` on the bar a short spread position is opened

Position state:

- **`position`**: `int64` — `+1` long spread, `-1` short spread, `0` flat
- **`entry_price`**: `float64` — listed-spread price the open position was entered at; `NaN` while flat
- **`position_age`**: `int64` — bars elapsed since entry, `0` while flat; drives the 30-minute time stop
- **`exit_flag`**: `bool` — `True` on the bar the position is closed
- **`exit_reason`**: `str` — `mean_reversion`, `stop_loss`, `time_stop`, or `session_end` on exit bars, otherwise null. Only `mean_reversion` (3) and `time_stop` (1) occur in the pilot week

P&L:

- **`position_pnl`**: `float64` — mark-to-market P&L of the open position at liquidating prices, reset to `0.0` on exit
- **`step_pnl`**: `float64` — change in `position_pnl` attributable to this bar; `0.0` while flat
- **`cum_pnl`**: `float64` — running sum of `step_pnl` across the whole backtest
