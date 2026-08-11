"""Plot backtest results for the Brent-WTI mean-reversion strategy.

Reads the results parquet written by strategy_engine.py and saves four PNGs
under OUTPUT_DIR/figures:

    strategy_01_spread_trades.png
    strategy_02_position.png
    strategy_03_cum_pnl.png
    strategy_04_trade_pnl.png

Usage:
    python src/plot_strategy_results.py
"""

import matplotlib

matplotlib.use("Agg")  # Headless-safe: never require a display.

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from settings import config
from strategy_engine import results_path


OUTPUT_DIR = config("OUTPUT_DIR")
FIGURES_DIR = OUTPUT_DIR / "figures"

FIGURE_NAMES = [
    "strategy_01_spread_trades",
    "strategy_02_position",
    "strategy_03_cum_pnl",
    "strategy_04_trade_pnl",
]


# Match the existing project plotting conventions.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SERIES = "#2a78d6"
MEAN = "#d38b1f"
BUY = "#006300"
SELL = "#d03b3b"
EXIT = "#6f42c1"


def load_results() -> pd.DataFrame:
    """Load the strategy results parquet."""
    path = results_path()

    if not path.exists():
        raise FileNotFoundError(
            f"Strategy results not found at {path}. "
            "Run `doit run_strategy` first."
        )

    return pd.read_parquet(path)


def _new_axes(title: str, ylabel: str):
    """Create a consistently styled figure and axes."""
    fig, ax = plt.subplots(figsize=(10, 4.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    ax.set_title(title, color=INK, loc="left", fontsize=12)
    ax.set_ylabel(ylabel, color=INK_2)
    ax.set_xlabel("UTC", color=INK_2)

    ax.grid(color=GRID, linewidth=0.8)
    ax.tick_params(colors=MUTED, labelsize=8)

    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)

    return fig, ax


def _save(fig, name: str):
    """Save and close one figure."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    path = FIGURES_DIR / f"{name}.png"

    fig.savefig(
        path,
        dpi=150,
        bbox_inches="tight",
        facecolor=SURFACE,
    )

    plt.close(fig)
    print(f"saved {path}")


def plot_spread_trades(results: pd.DataFrame):
    """Plot the signal spread, rolling mean, entries, and exits."""
    fig, ax = _new_axes(
        "Brent-WTI synthetic spread with strategy trades",
        "Spread price (USD/bbl)",
    )

    ax.plot(
        results.index,
        results["synth_mid"],
        color=SERIES,
        linewidth=1.1,
        label="Synthetic spread",
        zorder=2,
    )

    ax.plot(
        results.index,
        results["rolling_mean"],
        color=MEAN,
        linewidth=1.0,
        alpha=0.85,
        label="Rolling mean",
        zorder=1,
    )

    long_entries = results[results["long_entry"].fillna(False)]
    short_entries = results[results["short_entry"].fillna(False)]
    exits = results[results["exit_flag"].fillna(False)]

    ax.plot(
        long_entries.index,
        long_entries["synth_mid"],
        "^",
        color=BUY,
        markersize=5,
        linestyle="none",
        label="Long entry",
        zorder=3,
    )

    ax.plot(
        short_entries.index,
        short_entries["synth_mid"],
        "v",
        color=SELL,
        markersize=5,
        linestyle="none",
        label="Short entry",
        zorder=3,
    )

    ax.plot(
        exits.index,
        exits["synth_mid"],
        "x",
        color=EXIT,
        markersize=5,
        linestyle="none",
        label="Exit",
        zorder=3,
    )

    ax.legend(
        loc="upper left",
        frameon=False,
        labelcolor=INK_2,
        fontsize=9,
    )

    _save(fig, FIGURE_NAMES[0])


def plot_position(results: pd.DataFrame):
    """Plot the held long, short, or flat position."""
    fig, ax = _new_axes(
        "Held listed-spread position",
        "Position (contracts)",
    )

    ax.step(
        results.index,
        results["position"].fillna(0),
        where="post",
        color=SERIES,
        linewidth=1.2,
    )

    ax.axhline(0, color=BASELINE, linewidth=1)
    ax.set_yticks([-1, 0, 1])

    _save(fig, FIGURE_NAMES[1])


def plot_cumulative_pnl(results: pd.DataFrame):
    """Plot cumulative executable mark-to-market PnL."""
    fig, ax = _new_axes(
        "Cumulative strategy PnL",
        "Cumulative PnL (USD)",
    )

    ax.plot(
        results.index,
        results["cum_pnl"].ffill().fillna(0),
        color=SERIES,
        linewidth=1.6,
    )

    ax.axhline(0, color=BASELINE, linewidth=1)

    _save(fig, FIGURE_NAMES[2])


def plot_trade_pnl(results: pd.DataFrame):
    """Plot realized PnL for each completed trade."""
    completed = results[results["exit_flag"].fillna(False)].copy()
    completed = completed.reset_index()

    fig, ax = _new_axes(
        "Realized PnL by completed trade",
        "Trade PnL (USD)",
    )

    if completed.empty:
        ax.text(
            0.5,
            0.5,
            "No completed trades",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=INK_2,
        )
    else:
        trade_numbers = np.arange(1, len(completed) + 1)

        ax.bar(
            trade_numbers,
            completed["position_pnl"],
        )

        ax.set_xlabel("Completed trade", color=INK_2)
        ax.axhline(0, color=BASELINE, linewidth=1)

    _save(fig, FIGURE_NAMES[3])


def main():
    results = load_results()

    plot_spread_trades(results)
    plot_position(results)
    plot_cumulative_pnl(results)
    plot_trade_pnl(results)


if __name__ == "__main__":
    main()
