FINM 37000 Group 6 Trading
==========================

## Authors

- Andrew Heekin (<andrewheekin@gmail.com>)
- Michael Dowling (<mcdowling@uchicago.edu>)
- Sam Zhang (<chenruiz@uchicago.edu>)
- Bhuvanesh Kodem (<bkodem@uchicago.edu>)

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

## Quick Start

The quickest way to run code in this repo is to use the following steps.

You must have TexLive (or another LaTeX distribution) installed on your computer and available in your path.
You can do this by downloading and installing it from here ([windows](https://tug.org/texlive/windows.html#install)
and [mac](https://tug.org/mactex/mactex-download.html) installers).


First, create a virtual environment and activate it:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```
Then install the dependencies:
```bash
pip install -r requirements.txt
```

Provide your data credentials (e.g. a [Databento](https://databento.com) API key with access to the CME Globex dataset) by copying the example environment file and editing it:
```bash
cp .env.example .env
# then edit .env and set DATABENTO_API_KEY=your_key_here
```

Finally, run the project tasks:
```bash
doit
```
And that's it!


### Other commands

#### Unit Tests and Doc Tests

You can run the unit test, including doctests, with the following command:
```
pytest --doctest-modules
```

You can build the documentation with:
```
rm ./src/.pytest_cache/README.md
jupyter-book build -W ./
```
Use `del` instead of rm on Windows


#### Setting Environment Variables

You can [export your environment variables](https://stackoverflow.com/questions/43267413/how-to-set-environment-variables-from-env-file)
from your `.env` files like so, if you wish. This can be done easily in a Linux or Mac terminal with the following command:
```bash
set -a  # automatically export all variables
source .env
set +a
```
On Windows (PowerShell):
```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') } }
```

### Formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting Python code.

```bash
# Auto-fix linting issues (e.g., unused imports, undefined names)
ruff check . --fix

# Format code (consistent style, spacing, line length)
ruff format .

# Sort imports, then fix linting issues, then format
ruff format . && ruff check --select I --fix . && ruff check --fix .
```

- `ruff check --fix` applies safe auto-fixes for linting violations
- `ruff format` formats code similar to Black
- `--select I` targets only import sorting rules (isort-compatible)

### General Directory Structure

 - The `assets` folder is used for things like hand-drawn figures or other
   pictures that were not generated from code. These things cannot be easily
   recreated if they are deleted.

 - The `_output` folder, on the other hand, contains dataframes and figures that are
   generated from code. The entire folder should be able to be deleted, because
   the code can be run again, which would again generate all of the contents.

 - The `data_manual` is for data that cannot be easily recreated. This data
   should be version controlled. Anything in the `_data` folder or in
   the `_output` folder should be able to be recreated by running the code
   and can safely be deleted.

 - I'm using the `doit` Python module as a task runner. It works like `make` and
   the associated `Makefile`s. To rerun the code, install `doit`
   (https://pydoit.org/) and execute the command `doit` from the `src`
   directory. Note that doit is very flexible and can be used to run code
   commands from the command prompt, thus making it suitable for projects that
   use scripts written in multiple different programming languages.

 - I'm using the `.env` file as a container for absolute paths that are private
   to each collaborator in the project. You can also use it for private
   credentials, if needed. It should not be tracked in Git.

### Data and Output Storage

I'll often use a separate folder for storing data. Any data in the data folder
can be deleted and recreated by rerunning the PyDoit command (the pulls are in
the dodo.py file). Any data that cannot be automatically recreated should be
stored in the "data_manual" folder. Because of the risk of manually-created data
getting changed or lost, I prefer to keep it under version control if I can.
Thus, data in the "_data" folder is excluded from Git (see the .gitignore file),
while the "data_manual" folder is tracked by Git.

Output is stored in the "_output" directory. This includes dataframes, charts, and
rendered notebooks. When the output is small enough, I'll keep this under
version control. I like this because I can keep track of how dataframes change as my
analysis progresses, for example.

Of course, the _data directory and _output directory can be kept elsewhere on the
machine. To make this easy, I always include the ability to customize these
locations by defining the path to these directories in environment variables,
which I intend to be defined in the `.env` file, though they can also simply be
defined on the command line or elsewhere. The `settings.py` is responsible for
loading these environment variables and doing some preprocessing on them.
The `settings.py` file is the entry point for all other scripts to these
definitions. That is, all code that references these variables and others are
loaded by importing `config`.

### Naming Conventions

 - **`pull_` vs `load_`**: Files or functions that pull data from an external
 data source are prepended with "pull_", as in "pull_fred.py". Functions that
 load data that has been cached in the "_data" folder are prepended with "load_".
 For example, inside of the `pull_CRSP_Compustat.py` file there is both a
 `pull_compustat` function and a `load_compustat` function. The first pulls from
 the web, whereas the other loads cached data from the "_data" directory.


### Dependencies and Virtual Environments

#### Working with `pip` requirements

This project uses `pip` with a virtual environment. Install requirements with:
```bash
pip install -r requirements.txt
```

To update the requirements file after adding new packages:
```bash
pip freeze > requirements.txt
```
