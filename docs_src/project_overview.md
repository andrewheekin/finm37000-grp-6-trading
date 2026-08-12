# Project Overview

## FINM 37000 Group 6 Trading

Relative-value mean-reversion trading strategy on the Brent-WTI crude oil
futures spread.

**Team:** Andrew Heekin, Michael Dowling, Sam Zhang, Bhuvanesh Kodem
**Repository:** <https://github.com/andrewheekin/finm37000-grp-6-trading>

| Section | Description |
|---------|-------------|
| Goals | Project objectives and success criteria |
| Data Sources | Description of datasets and how they are obtained |
| Methodology | Approach, methods, and implementation details |

```{toctree}
:maxdepth: 1
:caption: Project Details

project_overview/goals
project_overview/data_sources
project_overview/methodology
```

## Status

- [x] Initialize project from template
- [x] Set up data pipeline and validate outputs
  ([issue #4](https://github.com/andrewheekin/finm37000-grp-6-trading/issues/4),
  [PR #21](https://github.com/andrewheekin/finm37000-grp-6-trading/pull/21))
- [x] Explore and document datasets — see [Data Pipeline](data_pipeline.md)
  and the dataframe pages in this site's catalog section
- [x] Build the diagnostic figures that motivate the design — see
  [Spread Diagnostics](spread_diagnostics.md)
- [x] Define entry rules (issue #13 signal generator)
- [x] Define exit rules and backtest the strategy — see
  [Strategy Overview](strategy_overview.md)
  ([PR #43](https://github.com/andrewheekin/finm37000-grp-6-trading/pull/43))
- [x] Report the backtest — see [Strategy Results](strategy_results.md)
- [ ] Extend the data window beyond the June 1-5 pilot week
- [ ] Revisit the ADF gate, which rejects 227 of 232 candidate entries on a
  30-bar window — see
  [Why only four trades](strategy_results.md#why-only-four-trades)
- [x] Write up findings — see the repository README
