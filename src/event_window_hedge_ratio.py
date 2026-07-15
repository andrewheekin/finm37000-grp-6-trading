"""Pull 1-minute CL/BZ event windows and run hedge-ratio diagnostics.

This script is intentionally separate from the MBP-1 pipeline.  It uses
Databento OHLCV 1-minute bars for short stress windows, which keeps the data
small enough for exploratory hedge-ratio checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import databento as db
import pandas as pd
import statsmodels.api as sm

from settings import config


DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1m"
SYMBOLS = ["CL.v.0", "BZ.v.0"]

DATA_DIR = config("DATA_DIR")
RAW_DIR = DATA_DIR / "databento_event_windows"
CLEAN_DIR = DATA_DIR / "event_windows"
OUTPUT_DIR = config("OUTPUT_DIR") / "event_windows"


@dataclass(frozen=True)
class EventWindow:
    name: str
    start: str
    end: str
    description: str


WINDOWS = [
    EventWindow(
        "covid_negative_wti",
        "2020-04-17",
        "2020-04-23",
        "COVID shock / WTI negative-price week",
    ),
    EventWindow(
        "covid_vaccine_reopen",
        "2020-11-06",
        "2020-11-12",
        "COVID vaccine/reopening repricing",
    ),
    EventWindow(
        "russia_ukraine_invasion",
        "2022-02-24",
        "2022-03-02",
        "Russia-Ukraine invasion shock",
    ),
    EventWindow(
        "non_conflict_baseline_2023",
        "2023-05-08",
        "2023-05-14",
        "Baseline week without a major new global conflict shock",
    ),
    EventWindow(
        "iran_israel_april_2024",
        "2024-04-12",
        "2024-04-18",
        "Iran-Israel April 2024 escalation",
    ),
    EventWindow(
        "iran_israel_june_2025",
        "2025-06-13",
        "2025-06-19",
        "Iran-Israel June 2025 escalation",
    ),
]


def _safe(text: str) -> str:
    return text.replace(".", "-").replace(":", "-").replace("/", "-").lower()


def raw_path(window: EventWindow) -> Path:
    symbols = "_".join(_safe(s) for s in SYMBOLS)
    return RAW_DIR / f"{window.name}_{symbols}_{SCHEMA}_{window.start}_{window.end}.dbn"


def aligned_path(window: EventWindow) -> Path:
    return CLEAN_DIR / f"{window.name}_cl_bz_1m_{window.start}_{window.end}.parquet"


def pull_window(window: EventWindow, client: db.Historical) -> Path:
    path = raw_path(window)
    if path.exists():
        print(f"cached   {window.name}: {path.name}")
        return path

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"pulling  {window.name}: {window.start} to {window.end}")
    data = client.timeseries.get_range(
        dataset=DATASET,
        symbols=SYMBOLS,
        stype_in="continuous",
        schema=SCHEMA,
        start=window.start,
        end=window.end,
    )
    data.to_file(path)
    print(f"saved    {window.name}: {path.name} ({path.stat().st_size / 1e6:.2f} MB)")
    return path


def align_window(window: EventWindow) -> pd.DataFrame:
    path = raw_path(window)
    df = db.DBNStore.from_file(path).to_df()

    if "symbol" not in df.columns:
        raise ValueError(f"{path} did not include a symbol column")
    if "close" not in df.columns:
        raise ValueError(f"{path} did not include OHLCV close prices")

    prices = df.pivot_table(values="close", index=df.index, columns="symbol", aggfunc="last")
    prices = prices.rename(columns={"CL.v.0": "cl_close", "BZ.v.0": "bz_close"})

    missing = {"cl_close", "bz_close"} - set(prices.columns)
    if missing:
        raise ValueError(
            f"{window.name} is missing expected columns {sorted(missing)}; "
            f"available symbols were {sorted(df['symbol'].dropna().unique())}"
        )

    aligned = prices[["cl_close", "bz_close"]].dropna().copy()
    aligned["synth_mid"] = aligned["cl_close"] - aligned["bz_close"]
    aligned["window"] = window.name
    aligned["description"] = window.description

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    aligned.to_parquet(aligned_path(window))
    return aligned


def diagnose_window(window: EventWindow, aligned: pd.DataFrame) -> dict[str, float | str | int]:
    y = aligned["cl_close"]
    x = aligned["bz_close"]

    level_model = sm.OLS(y, sm.add_constant(x)).fit()
    level_beta = float(level_model.params["bz_close"])
    level_alpha = float(level_model.params["const"])
    level_resid = y - (level_alpha + level_beta * x)

    returns = aligned[["cl_close", "bz_close"]].diff().dropna()
    return_model = sm.OLS(returns["cl_close"], sm.add_constant(returns["bz_close"])).fit()

    spread_1to1 = aligned["synth_mid"]

    return {
        "window": window.name,
        "description": window.description,
        "start": window.start,
        "end_exclusive": window.end,
        "rows": len(aligned),
        "cl_start": float(y.iloc[0]),
        "cl_end": float(y.iloc[-1]),
        "bz_start": float(x.iloc[0]),
        "bz_end": float(x.iloc[-1]),
        "level_alpha": level_alpha,
        "level_beta": level_beta,
        "level_r2": float(level_model.rsquared),
        "return_beta": float(return_model.params["bz_close"]),
        "return_r2": float(return_model.rsquared),
        "corr_levels": float(y.corr(x)),
        "corr_returns": float(returns["cl_close"].corr(returns["bz_close"])),
        "spread_mean": float(spread_1to1.mean()),
        "spread_std": float(spread_1to1.std()),
        "spread_min": float(spread_1to1.min()),
        "spread_max": float(spread_1to1.max()),
        "ols_resid_std": float(level_resid.std()),
        "ols_std_improvement_vs_1to1": 1 - float(level_resid.std()) / float(spread_1to1.std()),
    }


def write_markdown(results: pd.DataFrame) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "hedge_ratio_event_windows.md"

    show = results[
        [
            "description",
            "start",
            "end_exclusive",
            "rows",
            "return_beta",
            "level_beta",
            "return_r2",
            "level_r2",
            "corr_returns",
            "spread_std",
            "ols_resid_std",
            "ols_std_improvement_vs_1to1",
        ]
    ].copy()
    show["return_beta"] = show["return_beta"].round(4)
    show["level_beta"] = show["level_beta"].round(4)
    show["return_r2"] = show["return_r2"].round(4)
    show["level_r2"] = show["level_r2"].round(4)
    show["corr_returns"] = show["corr_returns"].round(4)
    show["spread_std"] = show["spread_std"].round(4)
    show["ols_resid_std"] = show["ols_resid_std"].round(4)
    show["ols_std_improvement_vs_1to1"] = show["ols_std_improvement_vs_1to1"].round(4)

    table_rows = [list(show.columns)] + show.astype(str).values.tolist()
    widths = [
        max(len(row[i]) for row in table_rows)
        for i in range(len(table_rows[0]))
    ]

    def table_line(row: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[i]) for i, value in enumerate(row)) + " |"

    markdown_table = "\n".join(
        [
            table_line(table_rows[0]),
            "| " + " | ".join("-" * width for width in widths) + " |",
            *[table_line(row) for row in table_rows[1:]],
        ]
    )

    lines = [
        "# Hedge Ratio Event Windows",
        "",
        "Data: Databento GLBX.MDP3, continuous `CL.v.0` and `BZ.v.0`, `ohlcv-1m`.",
        "End dates are exclusive.",
        "",
        markdown_table,
        "",
        "Interpretation notes:",
        "",
        "- `return_beta` near 1 supports a static 1:1 hedge ratio.",
        "- `return_r2` and `corr_returns` measure short-horizon co-movement in price changes.",
        "- `ols_std_improvement_vs_1to1` is in-sample residual volatility reduction from level OLS.",
        "",
    ]
    path.write_text("\n".join(lines))
    return path


def main() -> None:
    client = db.Historical(config("DATABENTO_API_KEY"))
    rows = []

    for window in WINDOWS:
        pull_window(window, client)
        aligned = align_window(window)
        rows.append(diagnose_window(window, aligned))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = pd.DataFrame(rows)
    csv_path = OUTPUT_DIR / "hedge_ratio_event_windows.csv"
    results.to_csv(csv_path, index=False)
    md_path = write_markdown(results)

    print(f"\nresults: {csv_path}")
    print(f"summary: {md_path}")
    print(
        results[
            [
                "window",
                "rows",
                "return_beta",
                "level_beta",
                "return_r2",
                "corr_returns",
                "ols_std_improvement_vs_1to1",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
