# Data Pipeline

The market-data pipeline
([issue #4](https://github.com/andrewheekin/finm37000-grp-6-trading/issues/4))
turns raw Databento MBP-1 events into cleaned, timestamp-aligned parquet
datasets. For a narrated tour with live output, see the **Brent-WTI Data
Pipeline Walkthrough** notebook (under Notebooks in this site's catalog
section).

## Steps

| Step | Module | What it does |
|------|--------|--------------|
| 0. Discovery | `src/instrument_discovery.py` | Confirms listed CL-BZ spread instruments exist, resolves roll dates per continuous rule, prices the pull before spending |
| 1. Pull | `src/pull_databento.py` | Pulls MBP-1 for `CL.v.0`, `BZ.v.0` and three listed spreads; caches raw DBN one file per symbol |
| 2. Clean/align | `src/clean_mbp1.py` | Events → 1s/1m grids (bounded forward-fill), listed-spread event series, and the aligned Brent-WTI dataset |
| 3. Diagnostics | `src/plot_spread_diagnostics.py` | Six mean-reversion figures — see [Spread Diagnostics](spread_diagnostics.md) |

Run everything with `doit`:

```
doit pull_databento      # Databento -> DBN cache (billable; cached pulls are skipped)
doit clean_mbp1          # cache -> parquet (grids, events, aligned)
doit spread_diagnostics  # figures -> _output/figures
doit run_notebooks       # execute + render the walkthrough notebook
```

## Output layout

`DATA_DIR` lives **outside** the repository (see `.env.example`); nothing
under it is committed.

```
DATA_DIR/
├── databento/          # raw DBN cache, one file per pull
│   └── glbx-mdp3_{symbol}_mbp-1_{start}_{end}.dbn
└── clean/              # parquet datasets built from the cache
    ├── {symbol}_{freq}_{start}_{end}.parquet          # per-instrument 1s/1m grids
    ├── {symbol}_events_{start}_{end}.parquet          # listed-spread event series
    └── brent_wti_aligned_{freq}_{start}_{end}.parquet # aligned dataset
```

## Loading the data

```python
from clean_mbp1 import load_aligned, load_grid, load_spread_events

aligned = load_aligned("1m")          # or "1s"
cl      = load_grid("CL.v.0", "1s")   # per-instrument grid
events  = load_spread_events()        # front listed spread, raw events
```

Column definitions and conventions: see the dataframe pages in this site's
catalog section (Brent-WTI Aligned 1-minute / 1-second, Listed Spread
Events) and
[Methodology](project_overview/methodology.md).

## Local `_data` junction (for chartbook data loading)

The chartbook manifest references data via the repo-relative path
`./_data/`, which is a local **junction** (Windows) or symlink pointing at
your external `DATA_DIR`. It is gitignored; create it once per machine:

```powershell
New-Item -ItemType Junction -Path _data -Target "C:\Users\<you>\data\finm37000-grp-6-trading\_data"
```

```bash
ln -s /path/to/your/data/_data _data
```

## Tests

`src/test_pipeline.py` — pure-function tests, no network or API key needed:

```
pytest src/test_pipeline.py
```
