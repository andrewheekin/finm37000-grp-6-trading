"""Visual mean-reversion diagnostics for the Brent-WTI spread (issue #4).

plotnine figures in the style of the FINM 33150 HW1 spread characterization:
week-view series colored by UTC time window with day separators, rolling-mean
deviation panels, annotated histogram with KDE and quantile lines, PACF bars,
and liquidity profiles by hour.

The question every figure addresses: does the spread visually mean-revert,
and at what horizon?

Usage:
    python src/plot_spread_diagnostics.py   # writes PNGs to OUTPUT_DIR/figures
"""

import numpy as np
import pandas as pd
import plotnine as p9
from scipy.stats import gaussian_kde
from statsmodels.tsa.stattools import pacf

from clean_mbp1 import load_aligned, load_grid
from pull_databento import OUTRIGHTS, SPREADS
from settings import config

OUTPUT_DIR = config("OUTPUT_DIR")
FIG_DIR = OUTPUT_DIR / "figures"

PAL = {
    "hist": "steelblue",
    "hist_border": "#2F4F4F",
    "density": "#DC143C",
    "shade": "#FFDAB9",
    "median": "#708090",
    "mean": "#4682B4",
    "text": "#333333",
}

# Rolling windows for the deviation panels: intraday horizons up to one day.
DEVIATION_WINDOWS = ["30min", "2h", "1D"]


def _four_hour_window(index: pd.DatetimeIndex) -> pd.Series:
    start = (index.hour // 4) * 4
    return pd.Series([f"{s:02d}:00-{s + 4:02d}:00" for s in start], index=index)


def _day_separators(plot, index, y_min, y_max):
    days = pd.date_range(
        index.min().normalize(),
        index.max().normalize() + pd.Timedelta(days=1),
        freq="D",
        tz=index.tz,
    )
    for ts in days:
        plot += p9.annotate(
            "segment", x=ts, xend=ts, y=y_min, yend=y_max,
            color="gray", linetype="dashed", size=0.5,
        )
        plot += p9.annotate(
            "text", x=ts, y=y_max, label=ts.strftime("%a %m/%d"),
            ha="left", va="top", size=7, color="gray",
        )
    return plot


def plot_week_series(series: pd.Series, title: str, ylabel: str) -> p9.ggplot:
    """Week view of one series, colored by 4-hour UTC window (HW1 style)."""
    df = series.dropna().to_frame("value")
    df["timestamp"] = df.index
    df["time window (UTC)"] = _four_hour_window(df.index)
    plot = (
        p9.ggplot(df, p9.aes(x="timestamp", y="value", color="time window (UTC)"))
        + p9.geom_point(size=0.5)
        + p9.theme_bw()
        + p9.theme(figure_size=(14, 4))
        + p9.labs(x="Date", y=ylabel, title=title)
    )
    return _day_separators(plot, df.index, df["value"].min(), df["value"].max())


def rolling_deviations(series: pd.Series, windows=DEVIATION_WINDOWS) -> pd.DataFrame:
    """Long frame of series minus its trailing mean, one panel per window."""
    frames = []
    for w in windows:
        dev = series - series.rolling(w).mean()
        frames.append(
            pd.DataFrame(
                {"timestamp": series.index, "deviation": dev, "window": w}
            )
        )
    out = pd.concat(frames).dropna()
    out["window"] = pd.Categorical(out["window"], categories=windows)
    return out


def plot_rolling_deviations(series: pd.Series, title: str) -> p9.ggplot:
    df = rolling_deviations(series)
    return (
        p9.ggplot(df, p9.aes(x="timestamp", y="deviation"))
        + p9.geom_line(size=0.3, color=PAL["mean"])
        + p9.geom_hline(yintercept=0, color=PAL["density"], linetype="dashed")
        + p9.facet_wrap("~window", ncol=1, scales="free_y")
        + p9.theme_bw()
        + p9.theme(figure_size=(14, 8))
        + p9.labs(x="Date", y="Spread - trailing mean ($/bbl)", title=title)
    )


def plot_histogram(series: pd.Series, title: str, xlabel: str, bins: int = 60) -> p9.ggplot:
    """Annotated histogram + KDE with mean/median and quantile lines (HW1 style)."""
    data = series.dropna()
    mean_val, median_val = data.mean(), data.median()
    q25, q75 = data.quantile(0.25), data.quantile(0.75)
    q025, q975 = data.quantile(0.025), data.quantile(0.975)
    kde = gaussian_kde(data)
    max_density = np.max(kde(np.linspace(data.min(), data.max(), 500)))
    y110, y130 = max_density * 1.10, max_density * 1.30

    df = data.to_frame("value")
    return (
        p9.ggplot(df, p9.aes(x="value"))
        + p9.annotate("rect", xmin=q25, xmax=q75, ymin=0, ymax=np.inf,
                      alpha=0.3, fill=PAL["shade"])
        + p9.geom_histogram(p9.aes(y=p9.after_stat("density")), bins=bins,
                            fill=PAL["hist"], color=PAL["hist_border"], alpha=0.4)
        + p9.geom_density(color=PAL["density"], size=1)
        + p9.geom_vline(xintercept=median_val, color=PAL["median"], linetype="dashed", size=1.2)
        + p9.geom_vline(xintercept=mean_val, color=PAL["mean"], linetype="dashed", size=1.2)
        + p9.geom_vline(xintercept=q025, color=PAL["density"], linetype="dotted", size=1.0)
        + p9.geom_vline(xintercept=q975, color=PAL["density"], linetype="dotted", size=1.0)
        + p9.annotate("text", x=mean_val, y=y110, label=f"Mean\n({mean_val:.4g})",
                      color=PAL["mean"], fontweight="bold", size=10, va="top", ha="right")
        + p9.annotate("text", x=median_val, y=y110, label=f"Median\n({median_val:.4g})",
                      color=PAL["median"], fontweight="bold", size=10, va="top", ha="left")
        + p9.annotate("text", x=q25, y=y130, label=f"Q1\n({q25:.4g})",
                      color=PAL["text"], size=9, va="top")
        + p9.annotate("text", x=q75, y=y130, label=f"Q3\n({q75:.4g})",
                      color=PAL["text"], size=9, va="top")
        + p9.annotate("text", x=q025, y=y130, label=f"2.5%\n({q025:.4g})",
                      color=PAL["text"], size=9, va="top", ha="right")
        + p9.annotate("text", x=q975, y=y130, label=f"97.5%\n({q975:.4g})",
                      color=PAL["text"], size=9, va="top", ha="left")
        + p9.theme_bw()
        + p9.theme(figure_size=(12, 4))
        + p9.labs(x=xlabel, y="Density", title=title)
    )


def plot_pacf(series: pd.Series, title: str, lags: int = 40) -> p9.ggplot:
    vals, confint = pacf(series.dropna(), nlags=lags, alpha=0.05)
    df = pd.DataFrame(
        {
            "lag": np.arange(len(vals)),
            "pacf": vals,
            "lower": confint[:, 0] - vals,
            "upper": confint[:, 1] - vals,
        }
    ).iloc[1:]  # lag 0 is 1 by definition
    return (
        p9.ggplot(df, p9.aes(x="lag", y="pacf"))
        + p9.geom_col(width=0.3, fill=PAL["hist"])
        + p9.geom_hline(yintercept=0, color="black")
        + p9.geom_ribbon(p9.aes(ymin="lower", ymax="upper"), alpha=0.2, fill="red")
        + p9.theme_bw()
        + p9.theme(figure_size=(12, 4))
        + p9.labs(x="Lag (minutes)", y="PACF", title=title)
    )


def plot_activity_by_hour(symbols=OUTRIGHTS + SPREADS) -> p9.ggplot:
    """Median top-of-book events per hour-of-day, one line per instrument."""
    frames = []
    for symbol in symbols:
        grid = load_grid(symbol, "1m")
        per_hour = grid.groupby([grid.index.date, grid.index.hour])["n_events"].sum()
        med = per_hour.groupby(level=1).median()
        frames.append(pd.DataFrame({"hour": med.index, "events": med.values, "instrument": symbol}))
    df = pd.concat(frames)
    df["instrument"] = pd.Categorical(df["instrument"], categories=symbols)
    return (
        p9.ggplot(df, p9.aes(x="hour", y="events", color="instrument"))
        + p9.geom_line(size=1)
        + p9.geom_point(size=1.5)
        + p9.scale_y_log10()
        + p9.theme_bw()
        + p9.theme(figure_size=(12, 4))
        + p9.labs(x="Hour of day (UTC)", y="Median events/hour (log scale)",
                  title="Top-of-book activity by hour - all instruments")
    )


def plot_width_by_hour(aligned: pd.DataFrame) -> p9.ggplot:
    """Median quoted width by hour: legged synthetic vs the listed books."""
    widths = pd.DataFrame(
        {
            "synthetic (legged)": aligned["synth_ask"] - aligned["synth_bid"],
            f"listed {SPREADS[0]}": aligned["ls_ask_px_00"] - aligned["ls_bid_px_00"],
        },
        index=aligned.index,
    )
    clq6 = load_grid(SPREADS[1], "1m")
    widths[f"listed {SPREADS[1]}"] = (
        (clq6["ask_px_00"] - clq6["bid_px_00"]).reindex(aligned.index)
    )
    med = widths.groupby(widths.index.hour).median()
    med.index.name = "hour"
    df = med.reset_index().melt(id_vars="hour", var_name="series", value_name="width")
    df["series"] = pd.Categorical(df["series"], categories=list(widths.columns))
    return (
        p9.ggplot(df, p9.aes(x="hour", y="width", color="series"))
        + p9.geom_line(size=1)
        + p9.geom_point(size=1.5)
        + p9.theme_bw()
        + p9.theme(figure_size=(12, 4))
        + p9.labs(x="Hour of day (UTC)", y="Median quoted width ($/bbl)",
                  title="Execution cost by hour: synthetic vs listed spread books")
    )


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    aligned = load_aligned("1m")
    synth = aligned["synth_mid"].dropna()

    figures = {
        "01_spread_week": plot_week_series(
            synth, "Brent-WTI synthetic spread (CL.v.0 - BZ.v.0), 1-minute mid", "Spread ($/bbl)"
        ),
        "02_rolling_deviations": plot_rolling_deviations(
            synth, "Spread minus trailing mean - does it pull back to zero?"
        ),
        "03_deviation_histogram": plot_histogram(
            rolling_deviations(synth, ["2h"])["deviation"],
            "Distribution of 2h-window deviations",
            "Spread - 2h trailing mean ($/bbl)",
        ),
        "04_pacf_deviation": plot_pacf(
            rolling_deviations(synth, ["2h"])["deviation"],
            "PACF - spread deviation from 2h trailing mean (1-minute lags)",
        ),
        "05_activity_by_hour": plot_activity_by_hour(),
        "06_width_by_hour": plot_width_by_hour(aligned),
    }
    for name, fig in figures.items():
        path = FIG_DIR / f"{name}.png"
        fig.save(path, dpi=150, verbose=False)
        print(f"saved {path.name}")
    print(f"\nFigures written to {FIG_DIR}")


if __name__ == "__main__":
    main()
