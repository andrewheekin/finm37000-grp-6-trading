# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 03. Entry Signal Generator Walkthrough
#
# This notebook documents the core entry signal for
# [issue #13](https://github.com/andrewheekin/finm37000-grp-6-trading/issues/13):
# a trailing rolling z-score on the 1-minute synthetic Brent–WTI spread
# (`synth_mid = cl_mid − bz_mid`), with long/short entries at $\pm 2\sigma$.
#
# Defaults: **30-minute** rolling window on 1-minute bars, entry at
# $\pm 2\sigma$. Exits are out of scope here (issue #15).

# %%
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from clean_mbp1 import load_aligned
from pull_databento import PILOT_END, PILOT_START
from settings import config
from signal_generator import (
    DEFAULT_ENTRY_Z,
    DEFAULT_WINDOW,
    generate_signals,
    signals_path,
)

OUTPUT_DIR = Path(config("OUTPUT_DIR"))
pd.set_option("display.max_columns", 40)
pd.set_option("display.width", 160)

print(f"Pilot window: {PILOT_START} to {PILOT_END} (end exclusive)")
print(f"Defaults: window={DEFAULT_WINDOW} bars, entry_z=±{DEFAULT_ENTRY_Z}")

# %% [markdown]
# ## 1. Load signals
#
# Prefer the pipeline parquet from `doit signal_generator`. Recompute from the
# aligned book if you want to tweak parameters interactively.

# %%
path = signals_path()
signals = pd.read_parquet(path)
print(f"loaded {path.name}: {len(signals):,} bars")
signals.head()

# %%
summary = pd.DataFrame(
    {
        "bars": [len(signals)],
        "valid": [int(signals["valid"].sum())],
        "long_entries": [int(signals["long_entry"].sum())],
        "short_entries": [int(signals["short_entry"].sum())],
        "valid_share": [signals["valid"].mean()],
    }
)
summary

# %% [markdown]
# ## 2. Z-score and entry markers
#
# Long entries (buy the spread: long CL / short BZ) fire when $z < -2$.
# Short entries fire when $z > +2$. Hygiene-invalid bars never enter.

# %%
plot_df = signals.dropna(subset=["zscore"]).copy()
longs = plot_df.loc[plot_df["long_entry"]]
shorts = plot_df.loc[plot_df["short_entry"]]

fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    subplot_titles=("Synthetic spread (synth_mid)", "Z-score with entry markers"),
)
fig.add_trace(
    go.Scatter(
        x=plot_df.index,
        y=plot_df["spread"],
        mode="lines",
        name="spread",
        line=dict(width=1, color="#4682B4"),
    ),
    row=1,
    col=1,
)
fig.add_trace(
    go.Scatter(
        x=plot_df.index,
        y=plot_df["zscore"],
        mode="lines",
        name="zscore",
        line=dict(width=1, color="#2F4F4F"),
    ),
    row=2,
    col=1,
)
fig.add_hline(y=DEFAULT_ENTRY_Z, line_dash="dash", line_color="gray", row=2, col=1)
fig.add_hline(y=-DEFAULT_ENTRY_Z, line_dash="dash", line_color="gray", row=2, col=1)
fig.add_trace(
    go.Scatter(
        x=longs.index,
        y=longs["zscore"],
        mode="markers",
        name="long entry",
        marker=dict(color="#228B22", size=7, symbol="triangle-up"),
    ),
    row=2,
    col=1,
)
fig.add_trace(
    go.Scatter(
        x=shorts.index,
        y=shorts["zscore"],
        mode="markers",
        name="short entry",
        marker=dict(color="#B22222", size=7, symbol="triangle-down"),
    ),
    row=2,
    col=1,
)
fig.update_layout(
    height=640,
    template="plotly_white",
    title="Issue #13 entry signals — pilot week (1m, 30-bar window, ±2 z)",
    hovermode="x unified",
)
fig.update_yaxes(title_text="$/bbl", row=1, col=1)
fig.update_yaxes(title_text="z", row=2, col=1)
fig

# %%
chart_path = OUTPUT_DIR / "03_signal_generator_zscore.html"
fig.write_html(chart_path)
print(f"Chart saved to: {chart_path}")

# %% [markdown]
# ## 3. Sanity check vs live `generate_signals`
#
# Recomputing from `load_aligned("1m")` should match the parquet row-for-row
# under the same defaults.

# %%
recomputed = generate_signals(load_aligned("1m"))
pd.testing.assert_frame_equal(signals, recomputed)
print("parquet matches generate_signals(load_aligned('1m'))")
