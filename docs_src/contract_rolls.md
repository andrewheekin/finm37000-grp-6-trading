# Contract Rolls

CL and BZ list monthly contracts, so each leg of the spread rolls ~12x/year
and the two legs roll on *different* dates
([issue #20](https://github.com/andrewheekin/finm37000-grp-6-trading/issues/20)).
A continuous series splices two contracts at each roll, injecting the
calendar-spread price into the series as a return the market never made.

The strategy is intraday and flat at EOD, so no position is ever held through
a roll. This is a statistics problem, not an execution problem.

## Roll rule

Continuous series use `.v.0` (volume-based roll), measured against the
alternatives over 2025-01 to 2026-07:

| Rule | Behaviour |
|------|-----------|
| `.n.0` (open interest) | Tracks highest OI across **all** expirations, so it repeatedly maps to December contracts rather than the front month |
| `.c.0` (calendar) | Deterministic, but holds the old contract several days after volume has left it |
| `.v.0` (volume) | Clean monthly ladder for CL (18 rolls, no whipsaw); near-clean for BZ, with brief flip-backs around some rolls |

## How large is the splice?

Measured by `src/roll_analysis.py` on the session before each roll, where the
outgoing and incoming contracts both trade, so the discontinuity is exact:

```
jump = close(incoming, prior_session) - close(outgoing, prior_session)
```

The spread's **roll-free** daily sigma is **0.566**. Computing sigma from the
raw continuous series instead gives 1.010 — inflated ~78% by the very jumps
being measured — so only diffs where neither leg rolled are used.

| Year | Leg | Rolls | Mean \|jump\| | Max |
|------|-----|-------|-------------|-----|
| 2025 | BZ | 16 | 1.11σ | 1.87σ |
| 2025 | CL | 12 | 1.08σ | 2.86σ |
| 2026 | BZ | 12 | 7.11σ | 14.08σ |
| 2026 | CL | 6 | 2.18σ | 7.31σ |

The 2026 figures come from a steep-backwardation regime (Brent ran 84 → 118
through March 2026); these are genuine trades, not stale closes — BZK6 traded
46,837 lots on the session behind the largest jump.

## Roll timing

The `.v.0` switch happens at the **00:00 UTC** calendar boundary, never
intraday — verified on the June 2026 rolls, where each leg shows exactly one
`instrument_id` per date.

Note 00:00 UTC is *mid-session*: Globex reopens at 22:00 UTC after the
maintenance break, and the hours either side of the boundary trade actively
(45 / 35 / 60 quoted 1m bars in the 22:00 / 23:00 / 00:00 hours on the CL roll
date). Windows therefore do straddle the boundary, and a date-level flag alone
is not sufficient.

The splice decomposes exactly. At the CL roll, `CL.v.0` moved −0.800 across
the boundary, of which −0.670 was the contemporaneous CLQ6−CLN6 spread and
−0.130 was genuine market movement.

## Convention: a window may never span a contract change

Because the legs roll on different dates, the unit that must stay constant is
the **pair** of held contracts, not either leg alone.

```python
from clean_mbp1 import load_aligned, regime_key, zscore_within_regime

aligned = load_aligned("1m")
regime  = regime_key(aligned)          # (cl_instrument_id, bz_instrument_id)
z       = zscore_within_regime(aligned["synth_mid"], regime, window="2h")
```

`rolling_within_regime` restarts the window at every roll, so the warm-up
after a roll is suppressed rather than computed from a handful of
observations.

### Any time scale

`window` takes either form, and the difference matters as soon as the grid
frequency changes:

- an **int** counts observations, so its duration is tied to the grid —
  `120` is two hours of the 1m grid but two minutes of the 1s grid;
- a **time offset** (`"2h"`, `"30min"`) is a real duration and means the same
  thing at every frequency, which is why it is the default.

Both grids suppress the identical 2h warm-up after a roll: 120 bars at 1m,
7200 at 1s.

### Flip-backs

Grouping on the contract pair alone would merge every occurrence of a pair
into one group, so a pair that recurs — which is what a flip-back is, e.g.
BZK6 → BZM6 → BZK6 five times in March 2026 — would let a window reach back
across the intervening contract as if nothing had happened. `regime_blocks`
numbers each *contiguous* run separately to prevent that.

## Why exclusion rather than back-adjustment

| Option | Verdict |
|--------|---------|
| Exclude spanning windows | **Adopted.** Exact, no estimation error, costs ~1.0% of the sample at a 120-minute window (47 contract-pair changes over 391 business days, ~1 per 8 sessions) |
| Back-adjust the legs | Makes cross-roll windows numerically usable, but they describe a spread level that was never tradeable |
| Estimate the jump from calendar spreads | Same objection, plus added estimation error |

Since the strategy never holds through a roll, the cross-roll windows that
back-adjustment would recover are not windows the strategy can act on. Dropping
whole `is_roll_date` sessions instead of using the pair key would cost ~12% of
the sample rather than ~1%.

`is_roll_date` in the cleaned parquet remains a correct but coarse superset of
the affected rows; prefer `regime_key` for anything statistical.

## Reproducing

```
doit instrument_discovery   # symbology -> _output/roll_dates_c_vs_n.csv
doit roll_analysis          # splice sizes + cost of the convention

python src/roll_analysis.py --mbp1   # adds the intraday June 2026 check (~93 MB)
```
