# Dataframe: `FI:brent_wti_aligned_1s` - Brent-WTI Aligned (1-second)

## Description

Identical layout to the Brent-WTI Aligned (1-minute) dataset, on a
1-second grid — ~430,000 rows over the pilot week. Intended for signal
work and microstructure checks where 1-minute buckets are too coarse.

```python
from clean_mbp1 import load_aligned
aligned = load_aligned("1s")
```

## Data Dictionary

See the Brent-WTI Aligned (1-minute) page — columns, conventions, and the
missing-data rules are identical; only the bucket size differs. The
600-second forward-fill limit spans 600 buckets on this grid (vs 10 on the
1-minute grid).



## DataFrame Glimpse

```
Rows: 421201
Columns: 35
$ cl_bid_px_00                   <f64> 90.2
$ cl_ask_px_00                   <f64> 90.4
$ cl_bid_sz_00                   <f64> 1.0
$ cl_ask_sz_00                   <f64> 1.0
$ cl_mid                         <f64> 90.30000000000001
$ cl_instrument_id               <f64> 777566.0
$ cl_n_events                    <i64> 1
$ cl_n_trades                    <i64> 0
$ cl_volume                      <u32> 0
$ cl_is_roll_date               <bool> False
$ bz_bid_px_00                   <f64> 92.69
$ bz_ask_px_00                   <f64> 93.5
$ bz_bid_sz_00                   <f64> 5.0
$ bz_ask_sz_00                   <f64> 30.0
$ bz_mid                         <f64> 93.095
$ bz_instrument_id               <f64> 755267.0
$ bz_n_events                    <i64> 1
$ bz_n_trades                    <i64> 0
$ bz_volume                      <u32> 0
$ bz_is_roll_date               <bool> False
$ ls_bid_px_00                   <f64> -4.0
$ ls_ask_px_00                   <f64> -2.45
$ ls_bid_sz_00                   <f64> 1.0
$ ls_ask_sz_00                   <f64> 3.0
$ ls_mid                         <f64> -3.225
$ ls_instrument_id               <f64> 42016777.0
$ ls_n_events                    <i64> 1
$ ls_n_trades                    <i64> 0
$ ls_volume                      <u32> 0
$ ls_is_roll_date               <bool> False
$ synth_mid                      <f64> -2.7949999999999875
$ synth_bid                      <f64> -3.299999999999997
$ synth_ask                      <f64> -2.289999999999992
$ is_roll_date                  <bool> False
$ ts_recv          <datetime[ns, UTC]> 2026-06-05 21:00:00+00:00


```

## Dataframe Manifest

| Dataframe Name                 | Brent-WTI Aligned (1-second)                                                   |
|--------------------------------|--------------------------------------------------------------------------------------|
| Dataframe ID                   | [brent_wti_aligned_1s](../dataframes/FI/brent_wti_aligned_1s.md)                                       |
| Data Sources                   | Databento GLBX.MDP3 (CME Globex), schema mbp-1                                        |
| Data Providers                 | Databento                                      |
| Links to Providers             | https://databento.com                             |
| Topic Tags                     | Brent, Wti, Futures, Spread, Market Data                                          |
| Type of Data Access            |                                   |
| How is data pulled?            | doit pull_databento clean_mbp1 (src/pull_databento.py -> src/clean_mbp1.py)                                                    |
| Data available up to (min)     | N/A                                                             |
| Data available up to (max)     | N/A                                                             |
| Dataframe Path                 | C:\Users\shpan\OneDrive\School\University of Chicago\Summer 2026\FINM 37000 - Futures and Related Derivatives\finm37000-grp-6-trading\_data\clean\brent_wti_aligned_1s_2026-06-01_2026-06-06.parquet                                                   |


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


