# finm37000-grp-6-trading

## Overview

FINM 37000 Summer '26 Group 6 is building a relative-value (spread) trading strategy and evaluating it in a backtest-and-report framework. Our primary strategy is an intraday mean-reversion trade on the Brent–WTI crude oil spread. As a secondary, exploratory track, we also test whether a cross-asset relationship between WTI and an interest-rate future is statistically tradeable using similar machinery.
Note: The goal is a methodologically sound strategy, not a profit-maximized one.
## Desired Outcome

Success for this project is a **reproducible, end-to-end research pipeline** that turns raw market data into a defensible verdict on the strategy — not a particular P&L number. By the end of the project we aim to deliver:

- **A clear answer to the central question:** does the Brent–WTI spread mean-revert at our chosen frequency, after realistic costs, and is that reversion stable enough to trade? The exploratory WTI / rate-future pair receives the same up-or-down verdict.
- **Reproducibility.** A teammate — or the grader — can clone the repository, supply their own data credentials, run a single command, and regenerate every figure and number in the report.
- **A documented decision trail.** Our choices (which pair, hedge-ratio method, parameters, sample window) are recorded with their rationale.
## Strategy Specification
Group 6's strategy is specified below. Items still under discussion are tracked in **Open Decisions**.

**Scope & Thesis**
1. **Products**: Brent (BZ) and WTI (CL) crude oil futures on CME Globex; optionally one interest-rate future (SR3) for the exploratory cross-asset leg.
2. **Type of Strategy**: Relative-value / statistical-arbitrage mean reversion on a stationary (locally cointegrated) spread.
3. **Holding Period**: Intraday, flat at end of session, contingent on the estimated half-life of mean reversion supporting an intraday horizon.
4. **Thesis**: A spread anchored by an economic relationship mean-reverts around a slowly-drifting equilibrium, and we trade deviations from it. The primary pair is Brent–WTI (both light, sweet crude); a WTI / rate-future pair is tested as a secondary hypothesis.

**Market Data**
1. Databento, CME Globex (`GLBX`) dataset, covering BZ, CL, and the chosen interest-rate future. Resolution (MBP-1 / 1-second / 1-minute) to be finalized against the holding period.
## Methodology
### 1. Spread construction & hedge ratio
- **Baseline:** static 1:1 spread.
- **Refinement:** estimated hedge ratio via total least squares / orthogonal regression (both legs are noisy, so plain OLS is direction-asymmetric).
- **Robustness:** rolling-window or Kalman-filtered dynamic hedge ratio, reported as a check on the baseline.
### 2. Fair value & signal
- Fair value = the spread's mean under **local** stationarity (rolling mean if the equilibrium drifts).
- Signal = **z-score** of the spread vs. its trailing mean/σ, with entry/exit bands (e.g. enter ±2σ, exit toward 0) and a risk stop.
### 3. Stationarity / cointegration testing
- **ADF and KPSS together** (complementary nulls).
- **Engle–Granger two-step** on the pair (regress one leg on the other, test the residual).
- **Rolling test as a trading gate:** only trade when the trailing window currently passes the stationarity tests.
- **Half-life** via AR(1) / Ornstein–Uhlenbeck: −ln(2) / ln(φ); sets the holding-period scale and checks whether an intraday version is viable.
### 4. Risk management
- Time-stop at a multiple of the half-life; end-of-session flatten; stationarity gate; volatility-scaled sizing.
- Note: in pure mean reversion a wider spread is a *stronger* signal, so a level-stop is protection against a broken stationarity assumption; payoffs are negatively skewed.
### 5. Backtest
- **No look-ahead:** all parameters estimated on data available up to each decision point (trailing/expanding window) or a clean train/test split.
- **Transaction costs:** Vary, starting at one tick + slippage per leg. Report drawdowns and the loss distribution, not just mean return.
## Interest-Rate Extension (Exploratory)
1. **Pair:** WTI (CL) vs. a chosen rate future (SR3).
2. **Hypothesis:** oil and yields are linked via inflation/growth channels, but the relationship is regime-dependent.
3. **Test cointegration:** a z-score on a non-cointegrated spread has no stable mean/variance to standardize against. 
4. **Hedge ratio:** no natural 1:1; size the rate leg by **DV01** against the oil notional.
5. **If it doesn't cointegrate:** report the negative result, optionally exploring other tradeable relationships between crude and interest rates.
## Open Decisions
- [ ] Data resolution / bar frequency in Databento.
- [ ] Backtest sample window and train/test split.
- [ ] Entry/exit band levels and stop parameters.
- [ ] Division of labor.
