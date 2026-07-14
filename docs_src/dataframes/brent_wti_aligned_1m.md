## Description

The headline dataset of the issue-4 pipeline: WTI (`CL.v.0`) and Brent
(`BZ.v.0`) top-of-book grids on one tz-aware UTC index at 1-minute buckets,
with the synthetic Brent-WTI spread computed from the legs and the front
exchange-listed spread instrument's book (`CLN6-BZQ6`) alongside. Pilot week
2026-06-01 to 2026-06-06 (end exclusive), ~7,000 rows.

Load it in analysis code with:

```python
from clean_mbp1 import load_aligned
aligned = load_aligned("1m")
```

(Requires the local data to exist — see the Data Pipeline page for
regeneration and the `_data` junction setup.)

## Conventions

- Quote columns are the last quote per bucket, forward-filled for at most
  600 seconds; buckets beyond that stay `NaN` (e.g. the daily maintenance
  break).
- `*_n_events == 0` marks a bucket whose quote is a carry-forward; activity
  columns are never forward-filled.
- Legs are combined with an outer join — no timestamps are dropped.

## Data Dictionary

Index: `ts_recv` — `datetime64[ns, UTC]`, 1-minute buckets.

Leg columns repeat per prefix: `cl_` (WTI leg), `bz_` (Brent leg), `ls_`
(front listed spread's book):

- **`{leg}_bid_px_00`**, **`{leg}_ask_px_00`**: `float64` — best bid/ask ($/bbl)
- **`{leg}_bid_sz_00`**, **`{leg}_ask_sz_00`**: `float64` — size at best bid/ask (contracts)
- **`{leg}_mid`**: `float64` — (bid + ask) / 2
- **`{leg}_instrument_id`**: `float64` — underlying contract id (tracks rolls)
- **`{leg}_n_events`**: `int64` — book events in the bucket (0 ⇒ quote carried forward)
- **`{leg}_n_trades`**: `int64` — trades in the bucket
- **`{leg}_volume`**: `float64` — contracts traded in the bucket
- **`{leg}_is_roll_date`**: `bool` — this leg's mapped contract changed on this date

Spread columns:

- **`synth_mid`**: `float64` — `cl_mid − bz_mid`, the synthetic spread
- **`synth_bid`**: `float64` — `cl_bid − bz_ask`, received selling the synthetic spread
- **`synth_ask`**: `float64` — `cl_ask − bz_bid`, paid buying the synthetic spread
- **`is_roll_date`**: `bool` — OR of the two legs' roll flags
