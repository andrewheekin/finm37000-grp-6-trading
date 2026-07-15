# Data Sources

## Overview

All market data comes from [Databento](https://databento.com), dataset
`GLBX.MDP3` (CME Globex MDP 3.0 feed), schema `mbp-1` — top-of-book quotes
and trades, one record per book event. Pulls are billable, so raw DBN files
are cached one-per-symbol and never deleted by the build system; data files
are not committed to the repository.

## Datasets

| Dataset | Source | Granularity | Description |
|---------|--------|-------------|-------------|
| `CL.v.0` | Databento GLBX.MDP3 | event-level (mbp-1) | WTI continuous front month, volume-based roll |
| `BZ.v.0` | Databento GLBX.MDP3 | event-level (mbp-1) | Brent continuous front month, volume-based roll |
| `CLN6-BZQ6`, `CLQ6-BZQ6`, `CLU6-BZU6` | Databento GLBX.MDP3 | event-level (mbp-1) | Exchange-listed Brent-WTI spread instruments (single order book each) |

**Sample window:** pilot week 2026-06-01 to 2026-06-06 (Mon-Fri, end
exclusive). The pipeline is parameterized by `start`/`end` for the full pull
later.

**Roll rule:** `.v.0` (volume-based). The open-interest rule (`.n.0`) was
measured to map to December contracts (highest open interest across all
expirations) rather than the front month — decision and measurements in
[issue #20](https://github.com/andrewheekin/finm37000-grp-6-trading/issues/20).

**Why the listed spread instruments matter:** they trade as single
instruments with their own book, so they are an execution venue for the
spread itself — one bid/ask rather than two legs to cross.

## Access and Licensing

- Requires a `DATABENTO_API_KEY` in `.env` (copy `.env.example`).
- Databento subscription terms do not permit redistributing raw data, which
  is one reason nothing under `DATA_DIR` is committed.
- The pilot-week pull is ~260 MB of raw DBN across the five symbols; cost
  was estimated ahead of time with `src/instrument_discovery.py`.

## Data Pipeline

See [Data Pipeline](../data_pipeline.md) for the pull → clean → align steps,
output layout, and how to load the datasets.
