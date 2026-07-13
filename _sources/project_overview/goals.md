# Goals

## Objectives

- Build and evaluate a relative-value mean-reversion strategy on the
  Brent-WTI crude oil futures spread (CL vs BZ on CME Globex).
- Ground every design decision in measurements on real market data rather
  than assumptions — instrument choice, execution venue, signal horizon, and
  transaction costs are all empirical questions.
- Keep the full pipeline reproducible: anyone on the team can regenerate the
  datasets, figures, and this documentation site from the repository plus a
  Databento API key.

## Success Criteria

- A cleaned, timestamp-aligned CL/BZ dataset that downstream analysis and
  trading code loads directly (delivered —
  [issue #4](https://github.com/andrewheekin/finm37000-grp-6-trading/issues/4)).
- A characterization of the spread's mean-reversion behavior (horizon,
  deviation distribution, autocorrelation structure) measured from the data
  — see [Spread Diagnostics](../spread_diagnostics.md).
- A backtested strategy with explicit entry/exit rules, realistic execution
  assumptions (synthetic vs listed spread books), and documented
  transaction-cost sensitivity.
- A final report and presentation for FINM 37000.

## Open Questions

- Which execution venue does a fill model assume: legging the synthetic
  spread through both outright books, or the exchange-listed spread
  instruments' own books? (The quoted-width-by-hour comparison in the
  diagnostics is the relevant measurement.)
- What sample period beyond the pilot week is needed for signal estimation
  and out-of-sample evaluation?
