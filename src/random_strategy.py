"""Placeholder random trading strategy on the front listed Brent-WTI spread (issue #38).

Rolls a seeded 3-sided die once per 1-minute bar of the CLN6-BZQ6 listed
spread book (from the issue #4 cleaned grids): buy -> target position +1,
sell -> target position -1, hold -> keep the current position. Positions are
marked to market on the bar mid, so bar PnL is the previous bar's position
times the change in mid (in spread price points per contract). No costs,
no fills, no sizing -- the strategy exists to exercise the pipeline
end-to-end, not to trade.

Output: DATA_DIR/strategy/random_{symbol}_1m.parquet with columns
    mid, action, position, bar_pnl, cum_pnl

Usage:
    python src/random_strategy.py
"""

import numpy as np
import pandas as pd

from clean_mbp1 import FRONT_SPREAD, _safe, load_grid
from settings import config

DATA_DIR = config("DATA_DIR")
STRATEGY_DIR = DATA_DIR / "strategy"

SYMBOL = FRONT_SPREAD  # CLN6-BZQ6
FREQ = "1m"
SEED = 37000  # fixed so every machine reproduces the same rolls

ACTIONS = np.array(["buy", "sell", "hold"])


def result_path(symbol: str = SYMBOL) -> "Path":
    return STRATEGY_DIR / f"random_{_safe(symbol)}_{FREQ}.parquet"


def run_strategy(mid: pd.Series, seed: int = SEED) -> pd.DataFrame:
    """Roll the die once per bar and account for the resulting positions.

    Parameters
    ----------
    mid : pd.Series
        Bar mid prices, indexed by bar timestamp. NaN bars (e.g. the daily
        maintenance break) are dropped before rolling.
    seed : int
        Seed for numpy's default_rng, so runs are reproducible.

    Returns
    -------
    pd.DataFrame with columns mid, action, position, bar_pnl, cum_pnl.
    The position takes effect at the end of its bar, so bar_pnl at t is
    position(t-1) * (mid(t) - mid(t-1)); the first bar's PnL is 0.
    """
    mid = mid.dropna()
    rng = np.random.default_rng(seed)
    action = pd.Series(rng.choice(ACTIONS, size=len(mid)), index=mid.index, name="action")

    target = action.map({"buy": 1.0, "sell": -1.0, "hold": np.nan})
    position = target.ffill().fillna(0.0)  # hold keeps prior position; flat before first trade

    bar_pnl = (position.shift(1) * mid.diff()).fillna(0.0)
    out = pd.DataFrame(
        {
            "mid": mid,
            "action": action,
            "position": position,
            "bar_pnl": bar_pnl,
            "cum_pnl": bar_pnl.cumsum(),
        }
    )
    return out


def load_results(symbol: str = SYMBOL) -> pd.DataFrame:
    path = result_path(symbol)
    if not path.exists():
        raise FileNotFoundError(
            f"No strategy results at {path}; run random_strategy.py first."
        )
    return pd.read_parquet(path)


def main():
    grid = load_grid(SYMBOL, FREQ)
    results = run_strategy(grid["mid"])
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    results.to_parquet(result_path())

    n_trades = (results["action"] != "hold").sum()
    print(
        f"{SYMBOL} {FREQ}: {len(results):,} bars, {n_trades:,} die-roll trades, "
        f"final cum PnL {results['cum_pnl'].iloc[-1]:+.3f} points"
    )
    print(f"written to {result_path()}")


if __name__ == "__main__":
    main()
