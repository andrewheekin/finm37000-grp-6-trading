# Data

## Manually-created data (`data_manual/`)

This folder holds manually created data that cannot be easily replicated.
Small files may be kept here under version control; use Git LFS if the data
is large. This project currently has no manual data — everything below is
pulled by code.

## Pulled market data (`DATA_DIR`, outside the repo)

All market data is pulled from Databento (dataset `GLBX.MDP3`, schema
`mbp-1`) by the issue-#4 pipeline and lives under `DATA_DIR`, which `.env`
points **outside** the repository (and outside OneDrive) — e.g.
`C:\Users\<user>\data\finm37000-grp-6-trading\_data`. Nothing under
`DATA_DIR` is committed.

### Instruments and window

- Continuous front months `CL.v.0` and `BZ.v.0` (volume-based roll — see
  issue #20 for the `.n.0` → `.v.0` decision and measurements).
- Exchange-listed same-month Brent-WTI spread instruments:
  `CLN6-BZQ6`, `CLQ6-BZQ6`, `CLU6-BZU6`.
- Pilot week `2026-06-01` to `2026-06-06` (end exclusive).

### Layout

```
DATA_DIR/
├── databento/          # raw DBN cache, one file per pull
│   └── glbx-mdp3_{symbol}_mbp-1_{start}_{end}.dbn
└── clean/              # parquet datasets built from the cache
    ├── {symbol}_{freq}_{start}_{end}.parquet          # per-instrument 1s/1m grids
    ├── {symbol}_events_{start}_{end}.parquet          # listed-spread event series
    └── brent_wti_aligned_{freq}_{start}_{end}.parquet # CL/BZ legs + synthetic + listed book
```

### Contract rolls (issue #20)

CL and BZ list monthly contracts, so each leg rolls ~12x/year and the two legs
roll on *different* dates. A continuous series splices two contracts at each
roll, which injects the calendar-spread price into the series as a return the
market never made.

**Rule.** Continuous series use `.v.0` (volume-based roll). `.n.0` tracks the
highest open interest across *all* expirations and repeatedly maps to December
contracts rather than the front month; `.c.0` holds the old contract several
days after volume has left it.

**Convention for rolling statistics: a window may never span a contract
change.** Because the legs roll on different dates, the unit that must stay
constant is the *pair* of held contracts, not either leg alone. Use:

```python
from clean_mbp1 import load_aligned, regime_key, zscore_within_regime

aligned = load_aligned("1m")
regime  = regime_key(aligned)                       # (cl_instrument_id, bz_instrument_id)
z       = zscore_within_regime(aligned["synth_mid"], regime, window="2h")
```

`rolling_within_regime` restarts the window at every roll, so a row whose
window would straddle a splice is NaN until a full window has accumulated in
the new stretch — the warm-up after each roll is suppressed rather than
computed from a handful of observations.

**Any time scale.** `window` takes either form, and the difference matters as
soon as the grid frequency changes:

- an **int** counts observations, so its duration is tied to the grid —
  `120` is two hours of the 1m grid but two minutes of the 1s grid;
- a **time offset** (`"2h"`, `"30min"`) is a real duration and means the same
  thing at every frequency, which is why it is the default.

Both grids are verified to suppress the identical 2h warm-up after a roll
(120 bars at 1m, 7200 at 1s).

**Flip-backs.** Grouping on the contract pair alone would merge every
occurrence of a pair into one group, so a pair that recurs — which is what a
flip-back is, e.g. BZK6 -> BZM6 -> BZK6 five times in March 2026 — would let a
window reach back across the intervening contract as if nothing had happened.
`regime_blocks` numbers each *contiguous* run separately to prevent that.

**Why exclusion rather than back-adjustment.** Measured over 2025-01 to
2026-07 by `src/roll_analysis.py` (artifacts: `_output/roll_jumps.csv`,
`_output/roll_contamination_cost.csv`):

- The spread's roll-free daily sigma is 0.566. Computing sigma from the raw
  continuous series instead gives 1.010 — inflated ~78% by the very jumps
  being measured, so roll-free diffs are used.
- Splice sizes: CL 18 rolls, mean |jump| 0.82; BZ 21 rolls plus 7 flip-backs,
  mean |jump| 1.67. In spread sigma that is 1.1 sigma (2025) rising to a mean
  of 7.1 and a max of 14.1 sigma for BZ in the steep-backwardation 2026
  regime.
- Excluding spanning windows costs ~1.0% of the sample at a 120-minute window
  (47 contract-pair changes over 391 business days, ~1 per 8 sessions).
  Dropping whole `is_roll_date` sessions instead would cost ~12%.

The strategy is intraday and flat at EOD, so no position is ever held through
a roll. Back-adjusting the legs, or estimating the jump from calendar-spread
prices, would make cross-roll windows numerically usable, but those windows
describe a spread level that was never tradeable — and they add estimation
error to buy back ~1% of the sample. If the tradeoff is worth revisiting, the
t-stats under each convention are directly comparable.

**Roll timing.** The `.v.0` switch happens at the 00:00 UTC calendar boundary,
never intraday (verified on the June 2026 rolls: one `instrument_id` per leg
per date). Note 00:00 UTC is *mid-session* — CME Globex reopens at 22:00 UTC
after the maintenance break — so windows do straddle the boundary with live
trading on both sides, and a date-level flag alone is not sufficient.

`is_roll_date` in the cleaned parquet remains a correct but coarse superset of
the affected rows; prefer `regime_key` for anything statistical.

### How to regenerate

Requires `DATABENTO_API_KEY` in `.env` (copy `.env.example`).

```
doit pull_databento   # billable pull; skips any symbol already in the DBN cache
doit clean_mbp1       # cache -> parquet (grids, spread events, aligned)
doit spread_diagnostics  # PNGs to OUTPUT_DIR/figures
```

Roll diagnostics are run separately, since they need the roll table from
`instrument_discovery.py` rather than the cleaned parquet:

```
python src/instrument_discovery.py   # writes _output/roll_dates_c_vs_n.csv
python src/roll_analysis.py          # splice sizes + cost of the convention
python src/roll_analysis.py --mbp1   # adds the intraday June 2026 roll check
```

Pulls are cached one DBN file per symbol/date-range, so re-running
`pull_databento` with a warm cache costs nothing, and `doit clean` never
deletes the DBN cache.
