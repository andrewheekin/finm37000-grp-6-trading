# Dataframe: `FI:entry_signals_1m` - Entry Signals (1-minute)

# Entry Signals (1-minute)

## Description

Entry signals for the Brent–WTI mean-reversion strategy (issue #13): trailing
rolling mean and standard deviation of the 1-minute synthetic spread
(`synth_mid`), z-score, and long/short entry flags when $|z|$ exceeds the
symmetric entry threshold (default $\pm 2$).

Defaults use a 30-bar (30-minute) window on 1-minute bars. Exits and position
state are left to issue #15; an optional `is_stationary` mask is supported in
the API for the future stationarity gate (issue #14) but is not applied in the
pipeline parquet.

Load it in analysis code with:

```python
import pandas as pd
from signal_generator import signals_path

signals = pd.read_parquet(signals_path())
```

Or regenerate from the aligned book:

```python
from clean_mbp1 import load_aligned
from signal_generator import signals_from_aligned

signals = signals_from_aligned(load_aligned("1m"))
```

Requires the local 1-minute aligned parquet (`doit clean_mbp1`) and
`doit signal_generator`.

## Conventions

- Rolling $\mu$ / $\sigma$ at time $t$ use the `window` bars ending at $t$,
  including $S_t$ itself, which is observed at decision time (no lookahead).
- Entries may re-fire on every threshold breach; no “already in trade”
  suppression.
- Hygiene blocks: NaN spread or legs, `is_roll_date`, carry-forward buckets
  (`cl_n_events == 0` or `bz_n_events == 0`), and near-zero rolling $\sigma$.
- Sign convention: $z > +2$ → short spread (`signal = -1`);
  $z < -2$ → long spread (`signal = +1`).

## Data Dictionary

Index: `ts_recv` — `datetime64[ns, UTC]`, 1-minute buckets (same as the
aligned source).

- **`spread`**: `float64` — synthetic mid used for the signal (`cl_mid − bz_mid`)
- **`rolling_mean`**: `float64` — trailing mean of the spread through the current bar
- **`rolling_std`**: `float64` — trailing sample standard deviation through the current bar
- **`zscore`**: `float64` — `(spread - rolling_mean) / rolling_std`
- **`entry_threshold`**: `float64` — absolute z threshold used (default `2.0`)
- **`long_entry`**: `bool` — `True` when `zscore < -entry_threshold` and valid
- **`short_entry`**: `bool` — `True` when `zscore > +entry_threshold` and valid
- **`signal`**: `int8` — `+1` long spread, `-1` short spread, `0` no entry
- **`valid`**: `bool` — hygiene (and optional stationarity) gate passed



## DataFrame Glimpse

```
Rows: 7021
Columns: 10
$ spread                        <f64> -2.7949999999999875
$ rolling_mean                  <f64> -2.6940000000000013
$ rolling_std                   <f64> 0.025877696427754414
$ zscore                        <f64> -3.9029749144000867
$ entry_threshold               <f64> 2.0
$ long_entry                   <bool> True
$ short_entry                  <bool> False
$ signal                         <i8> 1
$ valid                        <bool> True
$ ts_recv         <datetime[ns, UTC]> 2026-06-05 21:00:00+00:00


```

## Dataframe Manifest

| Dataframe Name                 | Entry Signals (1-minute)                                                   |
|--------------------------------|--------------------------------------------------------------------------------------|
| Dataframe ID                   | [entry_signals_1m](../dataframes/FI/entry_signals_1m.md)                                       |
| Data Sources                   | Brent-WTI aligned 1-minute parquet (issue #4 pipeline)                                        |
| Data Providers                 | Derived from Databento GLBX.MDP3 mbp-1                                      |
| Links to Providers             | https://databento.com                             |
| Topic Tags                     | Brent, Wti, Futures, Spread, Signals, Mean Reversion                                          |
| Type of Data Access            |                                   |
| How is data pulled?            | doit signal_generator (src/signal_generator.py <- clean_mbp1 aligned 1m)                                                    |
| Data available up to (min)     | N/A                                                             |
| Data available up to (max)     | N/A                                                             |
| Dataframe Path                 | /Users/andrewheekin/heekscripts/uchicago/2026q3_finm37000_futures_derivatives/finm37000-grp-6-trading/_output/brent_wti_signals_1m.parquet                                                   |


**Linked Charts:**

- None


## Pipeline Manifest

| Pipeline Name                   | FINM 37000 Group 6 Trading                       |
|---------------------------------|--------------------------------------------------------|
| Pipeline ID                     | [FI](../../../index.md)              |
| Lead Pipeline Developer         | Andrew Heekin, Michael Dowling, Sam Zhang, Bhuvanesh Kodem             |
| Contributors                    | Andrew Heekin, Michael Dowling, Sam Zhang, Bhuvanesh Kodem           |
| Git Repo URL                    | https://github.com/andrewheekin/finm37000-grp-6-trading                        |
| Pipeline Web Page               | <a href="https://andrewheekin.github.io/finm37000-grp-6-trading/">Pipeline Web Page      |
| Date of Last Code Update        | 2026-08-12 08:08:03           |
| OS Compatibility                |  |
| Linked Dataframes               |  [FI:brent_wti_aligned_1m](../../dataframes/FI/brent_wti_aligned_1m.md)<br>  [FI:brent_wti_aligned_1s](../../dataframes/FI/brent_wti_aligned_1s.md)<br>  [FI:spread_events_front](../../dataframes/FI/spread_events_front.md)<br>  [FI:entry_signals_1m](../../dataframes/FI/entry_signals_1m.md)<br>  [FI:brent_wti_strategy_1m](../../dataframes/FI/brent_wti_strategy_1m.md)<br>  |


