"""Sample plots for the placeholder random strategy (issue #38).

Reads the strategy results parquet written by random_strategy.py and saves
three PNGs to OUTPUT_DIR/figures:

    random_strategy_01_price_trades.png  -- spread mid with position-change markers
    random_strategy_02_position.png      -- held position through the week
    random_strategy_03_cum_pnl.png       -- cumulative mark-to-market PnL

Usage:
    python src/plot_random_strategy.py
"""

import matplotlib

matplotlib.use("Agg")  # headless-safe: never require a display
import matplotlib.pyplot as plt

from random_strategy import FREQ, SYMBOL, load_results
from settings import config

OUTPUT_DIR = config("OUTPUT_DIR")
FIGURES_DIR = OUTPUT_DIR / "figures"

FIGURE_NAMES = [
    "random_strategy_01_price_trades",
    "random_strategy_02_position",
    "random_strategy_03_cum_pnl",
]

# Palette (validated light-mode set from the project dataviz conventions)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SERIES = "#2a78d6"  # blue: price / position / PnL lines
BUY = "#006300"  # green up-triangle at new long positions
SELL = "#d03b3b"  # red down-triangle at new short positions


def _new_axes(title: str, ylabel: str):
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
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"saved {path}")


def plot_price_trades(results):
    """Spread mid over the pilot week, marking bars where the position changed."""
    fig, ax = _new_axes(
        f"{SYMBOL} spread mid ({FREQ} bars) with random-die position changes",
        "Spread price (USD/bbl)",
    )
    ax.plot(results.index, results["mid"], color=SERIES, linewidth=1.2, zorder=2)

    changed = results["position"].diff().fillna(results["position"]) != 0
    to_long = results[changed & (results["position"] > 0)]
    to_short = results[changed & (results["position"] < 0)]
    ax.plot(
        to_long.index, to_long["mid"], "^", color=BUY, markersize=4,
        alpha=0.7, linestyle="none", label="flip to long", zorder=3,
    )
    ax.plot(
        to_short.index, to_short["mid"], "v", color=SELL, markersize=4,
        alpha=0.7, linestyle="none", label="flip to short", zorder=3,
    )
    ax.legend(loc="upper left", frameon=False, labelcolor=INK_2, fontsize=9)
    _save(fig, FIGURE_NAMES[0])


def plot_position(results):
    fig, ax = _new_axes(
        f"Held position, {SYMBOL} ({FREQ} bars)", "Position (contracts)"
    )
    ax.step(results.index, results["position"], where="post", color=SERIES, linewidth=1.2)
    ax.axhline(0, color=BASELINE, linewidth=1)
    ax.set_yticks([-1, 0, 1])
    _save(fig, FIGURE_NAMES[1])


def plot_cum_pnl(results):
    fig, ax = _new_axes(
        f"Cumulative mark-to-market PnL, {SYMBOL} ({FREQ} bars)",
        "Cumulative PnL (spread points / contract)",
    )
    ax.plot(results.index, results["cum_pnl"], color=SERIES, linewidth=1.6)
    ax.axhline(0, color=BASELINE, linewidth=1)
    _save(fig, FIGURE_NAMES[2])


def main():
    results = load_results()
    plot_price_trades(results)
    plot_position(results)
    plot_cum_pnl(results)


if __name__ == "__main__":
    main()
