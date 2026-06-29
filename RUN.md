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
