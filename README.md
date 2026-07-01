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
6. **Thesis**: A spread anchored by an economic relationship mean-reverts around a slowly-drifting equilibrium, and we trade deviations from it. The primary pair is Brent–WTI (both light, sweet crude); a WTI / rate-future pair could be tested as a secondary hypothesis.

**Market Data**
1. Databento, CME Globex (`GLBX`) dataset, covering BZ, CL, and a chosen interest-rate future if desired. Resolution (MBP-1 / 1-second / 1-minute / etc.) to be finalized against the holding period.
## Methodology
### 1. Spread construction & hedge ratio
- **Baseline:** static 1:1 spread given that the underlying is the same for both Brent and WTI.
### 2. Fair value & signal
- Fair value = the spread's mean under **local** stationarity (rolling mean if the equilibrium drifts).
- Signal = **z-score** of the spread vs. its trailing mean/σ, with entry/exit bands (e.g. enter ±2σ, exit toward 0) and a risk stop.
### 3. Stationarity testing
- **Possible tests for stationarity**
  - **ADF and KPSS together** (complementary nulls).
  - **Engle–Granger two-step** on the pair (regress one leg on the other, test the residual).
- **Half-life** via AR(1) / Ornstein–Uhlenbeck: −ln(2) / ln(φ); sets the holding-period scale and checks whether an intraday version is viable.
### 4. Risk management
- Potential strategies: Time-stop at a multiple of the half-life; end-of-session flatten (i.e. intraday trading); stationarity gate; volatility-scaled sizing (i.e. consistent risk profile).
- Note: in pure mean reversion a wider spread is a *stronger* signal, so a level-stop is protection against a broken stationarity assumption; payoffs are negatively skewed.
### 5. Backtest
- **No look-ahead:** all parameters estimated on data available up to each decision point (trailing/expanding window) or a clean train/test split.
- **Transaction costs:** Vary, starting at one tick + slippage per leg. Report drawdowns and the loss distribution, not just mean return.
## Extensions (Exploratory)

Optional tracks that build on the primary Brent–WTI strategy. Full team discussion and attribution are in [DISCUSSION.md](DISCUSSION.md).

### A+ — Macro-gated Brent–WTI (Sam Zhang)

Keep the Brent–WTI core, but gate entries and sizing with macro signals:

- **Regime filter:** use interest-rate futures to avoid trading during large macro-driven rate moves.
- **VIX-adjusted entry:** widen or tighten z-score entry bands based on implied volatility.
- **Exit refinement:** evaluate explicit exit rules beyond revert-to-mean — e.g. |z| < 0.5, velocity/acceleration of z-score, half-life time-stop, vol spike, rolling stationarity failure, or modeled reversion probability.

### B — Oil–rates cross-asset reversion (Andrew Heekin)

Standalone cross-asset mean reversion on WTI (CL) and front-end rates (SR3):

- **Pair & signal:** trade CL–SR3 when the oil–rates relationship stretches (z-score entry/exit, same statistical framework as the primary strategy).
- **Hypothesis:** oil and yields are linked via inflation & growth channels, but the relationship is regime-dependent — test cointegration before trading; a z-score on a non-cointegrated spread has no stable mean/variance to standardize against.
- **Brent–WTI filter:** only take CL–SR3 trades when Brent–WTI is stable (no geographic dislocation), to avoid double-counting an energy shock.
- **Negative result:** if the pair does not cointegrate, report that outcome rather than forcing a trade.

## Running the Project

> **Draft / placeholder.** The structure and commands below describe the *intended* workflow and will be updated as the code is developed. They are a target, not yet a working pipeline.

### Prerequisites
- Python 3.11+
- A [Databento](https://databento.com) API key with access to the CME Globex dataset (`GLBX.MDP3`)
- `git`

### Setup
```bash
# 1. Clone the repository
git clone https://github.com/andrewheekin/finm37000-grp-6-trading.git
cd finm37000-grp-6-trading

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Provide your Databento credentials
cp .env.example .env
# then edit .env and set DATABENTO_API_KEY=your_key_here
```

### Configuration
Strategy parameters live in `config.yaml` — instruments, sample window, bar resolution, z-score bands, and stop settings:
```yaml
instruments: [CL, BZ]          # swap in SR3 or ZN for the rate-extension run
start: 2023-01-01
end:   2024-12-31
resolution: 1m                 # 1-minute bars
entry_z: 2.0                   # enter when |z| exceeds this
exit_z:  0.0                   # exit as the spread reverts toward its mean
window:  60                    # trailing window (days) for mean/σ and the stationarity gate
```

### Workflow
```bash
# 1. Pull market data from Databento into ./data
python -m src.data.fetch

# 2. Build the spread; run cointegration and half-life diagnostics
python -m src.research.diagnostics

# 3. Generate signals and run the backtest (transaction costs included)
python -m src.backtest.run

# 4. Build the report (figures + metrics) into ./reports
python -m src.report.build
```

Outputs land in `./reports/`: a performance summary, the equity curve, a trade log, and the stationarity / half-life diagnostics. To run the exploratory interest-rate pair, set `instruments: [CL, SR3]` in `config.yaml` and re-run the workflow.
