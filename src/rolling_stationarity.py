"""Reusable rolling ADF/KPSS stationarity tests for backtesting.

Each rolling result is labeled at the final observation in its window, so the
signal can be used at that timestamp or later without look-ahead bias.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import warnings

import pandas as pd
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.stattools import adfuller, kpss


@dataclass(frozen=True)
class StationarityResult:
    """Result of applying ADF and KPSS to one window."""

    n_observations: int
    adf_pvalue: float | None
    kpss_pvalue: float | None
    passes_adf: bool
    passes_kpss: bool
    is_stationary: bool
    valid_test: bool
    error: str | None = None


def stationarity_test(
    series: pd.Series,
    *,
    adf_alpha: float = 0.05,
    kpss_alpha: float = 0.05,
    min_observations: int = 20,
) -> StationarityResult:
    """Test one spread window for stationarity using both ADF and KPSS.

    A window passes when ADF rejects its unit-root null hypothesis and KPSS
    does not reject its level-stationarity null hypothesis. Missing values are
    removed before testing.
    """
    _validate_alpha("adf_alpha", adf_alpha)
    _validate_alpha("kpss_alpha", kpss_alpha)
    if min_observations < 5:
        raise ValueError("min_observations must be at least 5")

    clean = pd.Series(series, copy=False).dropna().astype(float)
    n_observations = len(clean)

    if n_observations < min_observations:
        return _invalid_result(
            n_observations,
            f"requires at least {min_observations} non-missing observations",
        )
    if clean.nunique() < 3:
        return _invalid_result(
            n_observations,
            "requires at least 3 unique observations",
        )

    try:
        if n_observations < 20:
            adf_pvalue = float(adfuller(clean, maxlag=0, autolag=None)[1])
        else:
            adf_pvalue = float(adfuller(clean, autolag="AIC")[1])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InterpolationWarning)
            kpss_pvalue = float(kpss(clean, regression="c", nlags="auto")[1])
    except (ValueError, FloatingPointError, ZeroDivisionError) as exc:
        return _invalid_result(n_observations, str(exc))

    passes_adf = adf_pvalue < adf_alpha
    passes_kpss = kpss_pvalue > kpss_alpha
    return StationarityResult(
        n_observations=n_observations,
        adf_pvalue=adf_pvalue,
        kpss_pvalue=kpss_pvalue,
        passes_adf=passes_adf,
        passes_kpss=passes_kpss,
        is_stationary=passes_adf and passes_kpss,
        valid_test=True,
    )


def rolling_stationarity_test(
    series: pd.Series,
    window: int,
    *,
    step: int = 1,
    adf_alpha: float = 0.05,
    kpss_alpha: float = 0.05,
    min_observations: int = 20,
) -> pd.DataFrame:
    """Run the combined ADF/KPSS test over fixed-size rolling windows.

    Parameters
    ----------
    series
        Spread observations in chronological order. Its index is preserved.
    window
        Number of observations in each rolling window.
    step
        Number of observations between consecutive window endpoints. Use
        ``step=1`` for fully overlapping windows or ``step=window`` for
        non-overlapping windows.

    Returns
    -------
    pandas.DataFrame
        One row per window, indexed by ``window_end``. Important columns are
        ``is_stationary`` and ``valid_test``.

    Examples
    --------
    >>> results = rolling_stationarity_test(spread, window=30, step=1)
    >>> trading_gate = results["is_stationary"]
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series")
    if not isinstance(window, int) or isinstance(window, bool) or window < 1:
        raise ValueError("window must be a positive integer")
    if not isinstance(step, int) or isinstance(step, bool) or step < 1:
        raise ValueError("step must be a positive integer")
    if window < min_observations:
        raise ValueError("window must be greater than or equal to min_observations")
    if not series.index.is_monotonic_increasing:
        raise ValueError("series index must be sorted in increasing order")

    rows: list[dict[str, object]] = []
    for end_position in range(window, len(series) + 1, step):
        sample = series.iloc[end_position - window : end_position]
        result = stationarity_test(
            sample,
            adf_alpha=adf_alpha,
            kpss_alpha=kpss_alpha,
            min_observations=min_observations,
        )
        row = asdict(result)
        row["window_start"] = sample.index[0]
        row["window_end"] = sample.index[-1]
        rows.append(row)

    columns = [
        "window_start",
        "window_end",
        "n_observations",
        "adf_pvalue",
        "kpss_pvalue",
        "passes_adf",
        "passes_kpss",
        "is_stationary",
        "valid_test",
        "error",
    ]
    output = pd.DataFrame(rows, columns=columns)
    return output.set_index("window_end")


def _invalid_result(n_observations: int, error: str) -> StationarityResult:
    return StationarityResult(
        n_observations=n_observations,
        adf_pvalue=None,
        kpss_pvalue=None,
        passes_adf=False,
        passes_kpss=False,
        is_stationary=False,
        valid_test=False,
        error=error,
    )


def _validate_alpha(name: str, value: float) -> None:
    if not 0 < value < 1:
        raise ValueError(f"{name} must be between 0 and 1")


__all__ = [
    "StationarityResult",
    "rolling_stationarity_test",
    "stationarity_test",
]
