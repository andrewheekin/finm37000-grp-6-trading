# Dataframe: `FI:spread_events_front` - Listed Spread Events (CLN6-BZQ6)

## Description

Raw cleaned top-of-book event series for the front exchange-listed
Brent-WTI spread instrument (`CLN6-BZQ6`) over the pilot week — every MBP-1
book event as it occurred, no gridding or forward-filling. This book *is*
the tradeable Brent-WTI spread, so its event sequence is stored as-is;
downstream code decides how to sample it.

```python
from clean_mbp1 import load_spread_events
events = load_spread_events()  # front spread by default
```

Event series for the other two listed spreads (`CLQ6-BZQ6`, `CLU6-BZU6`)
exist under the same naming scheme:
`load_spread_events("CLQ6-BZQ6")`.

## Data Dictionary

Index: `ts_recv` — `datetime64[ns, UTC]`, one row per book event.

- **`instrument_id`**: `uint32` — the spread instrument's id
- **`action`**: `str` — MBP-1 action code (`A` add, `C` cancel, `M` modify, `T` trade, ...)
- **`side`**: `str` — side of the event (`B` bid, `A` ask, `N` none)
- **`price`**: `float64` — event price ($/bbl; spread prices are typically negative, Brent over WTI)
- **`size`**: `float64` — event size (contracts)
- **`bid_px_00`**, **`ask_px_00`**: `float64` — best bid/ask after the event
- **`bid_sz_00`**, **`ask_sz_00`**: `float64` — size at best bid/ask after the event
- **`mid`**: `float64` — (bid + ask) / 2
- **`is_crossed`**: `bool` — bid ≥ ask (flagged, not dropped)



## DataFrame Glimpse

```
Rows: 624789
Columns: 12
$ instrument_id               <u32> 42016777
$ action                      <str> 'C'
$ side                        <str> 'N'
$ price                       <f64> -2.45
$ size                        <u32> 1
$ bid_px_00                   <f64> -4.0
$ ask_px_00                   <f64> -2.45
$ bid_sz_00                   <u32> 1
$ ask_sz_00                   <u32> 3
$ mid                         <f64> -3.225
$ is_crossed                 <bool> False
$ ts_recv       <datetime[ns, UTC]> 2026-06-05 21:00:00.185201+00:00


```

## Dataframe Manifest

| Dataframe Name                 | Listed Spread Events (CLN6-BZQ6)                                                   |
|--------------------------------|--------------------------------------------------------------------------------------|
| Dataframe ID                   | [spread_events_front](../dataframes/FI/spread_events_front.md)                                       |
| Data Sources                   | Databento GLBX.MDP3 (CME Globex), schema mbp-1                                        |
| Data Providers                 | Databento                                      |
| Links to Providers             | https://databento.com                             |
| Topic Tags                     | Brent, Wti, Futures, Spread, Market Data, Microstructure                                          |
| Type of Data Access            |                                   |
| How is data pulled?            | doit pull_databento clean_mbp1 (src/pull_databento.py -> src/clean_mbp1.py)                                                    |
| Data available up to (min)     | N/A                                                             |
| Data available up to (max)     | N/A                                                             |
| Dataframe Path                 | C:\Users\shpan\OneDrive\School\University of Chicago\Summer 2026\FINM 37000 - Futures and Related Derivatives\finm37000-grp-6-trading\_data\clean\cln6-bzq6_events_2026-06-01_2026-06-06.parquet                                                   |


**Linked Charts:**

- None


## Pipeline Manifest

| Pipeline Name                   | FINM 37000 Group 6 Trading                       |
|---------------------------------|--------------------------------------------------------|
| Pipeline ID                     | [FI](../../../index.md)              |
| Lead Pipeline Developer         | Andrew Heekin, Michael Dowling, Sam Zhang, Bhuvanesh Kodem             |
| Contributors                    | Andrew Heekin, Michael Dowling, Sam Zhang, Bhuvanesh Kodem           |
| Git Repo URL                    | https://github.com/andrewheekin/finm37000-grp-6-trading                        |
| Pipeline Web Page               | <a href="file://C:/Users/shpan/OneDrive/School/University of Chicago/Summer 2026/FINM 37000 - Futures and Related Derivatives/finm37000-grp-6-trading/docs/index.html">Pipeline Web Page      |
| Date of Last Code Update        | 2026-07-13 11:50:43           |
| OS Compatibility                |  |
| Linked Dataframes               |  [FI:brent_wti_aligned_1m](../../dataframes/FI/brent_wti_aligned_1m.md)<br>  [FI:brent_wti_aligned_1s](../../dataframes/FI/brent_wti_aligned_1s.md)<br>  [FI:spread_events_front](../../dataframes/FI/spread_events_front.md)<br>  |


