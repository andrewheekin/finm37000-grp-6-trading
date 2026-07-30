## Description

Entry signals for the Brent–WTI mean-reversion strategy (issue #13): past-only
rolling mean and standard deviation of the 1-minute synthetic spread
(`synth_mid`), z-score, and long/short entry flags when $|z|$ exceeds the
symmetric entry threshold (default $\pm 2$).

Defaults use a 30-bar (30-minute) window on 1-minute bars. Exits and position
state are left to issue #15; an optional `is_stationary` mask is supported in
the API for the future stationarity gate (issue #14) but is not applied in the
pipeline parquet.

Load it in analysis code with:

```python
import pandas as pd
from signal_generator import signals_path

signals = pd.read_parquet(signals_path())
```

Or regenerate from the aligned book:

```python
from clean_mbp1 import load_aligned
from signal_generator import signals_from_aligned

signals = signals_from_aligned(load_aligned("1m"))
```

Requires the local 1-minute aligned parquet (`doit clean_mbp1`) and
`doit signal_generator`.

## Conventions

- Rolling $\mu$ / $\sigma$ at time $t$ use only bars before $t$
  (`shift(1).rolling`), so the decision bar is not in its own window.
- Entries may re-fire on every threshold breach; no “already in trade”
  suppression.
- Hygiene blocks: NaN spread or legs, `is_roll_date`, carry-forward buckets
  (`cl_n_events == 0` or `bz_n_events == 0`), and near-zero rolling $\sigma$.
- Sign convention: $z > +2$ → short spread (`signal = -1`);
  $z < -2$ → long spread (`signal = +1`).

## Data Dictionary

Index: `ts_recv` — `datetime64[ns, UTC]`, 1-minute buckets (same as the
aligned source).

- **`spread`**: `float64` — synthetic mid used for the signal (`cl_mid − bz_mid`)
- **`rolling_mean`**: `float64` — past-only trailing mean of the spread
- **`rolling_std`**: `float64` — past-only trailing sample standard deviation
- **`zscore`**: `float64` — `(spread - rolling_mean) / rolling_std`
- **`entry_threshold`**: `float64` — absolute z threshold used (default `2.0`)
- **`long_entry`**: `bool` — `True` when `zscore < -entry_threshold` and valid
- **`short_entry`**: `bool` — `True` when `zscore > +entry_threshold` and valid
- **`signal`**: `int8` — `+1` long spread, `-1` short spread, `0` no entry
- **`valid`**: `bool` — hygiene (and optional stationarity) gate passed
