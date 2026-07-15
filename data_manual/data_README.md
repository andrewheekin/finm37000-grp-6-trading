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

### How to regenerate

Requires `DATABENTO_API_KEY` in `.env` (copy `.env.example`).

```
doit pull_databento   # billable pull; skips any symbol already in the DBN cache
doit clean_mbp1       # cache -> parquet (grids, spread events, aligned)
doit spread_diagnostics  # PNGs to OUTPUT_DIR/figures
```

Pulls are cached one DBN file per symbol/date-range, so re-running
`pull_databento` with a warm cache costs nothing, and `doit clean` never
deletes the DBN cache.
