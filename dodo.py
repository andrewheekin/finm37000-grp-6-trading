"""Run or update the project. This file uses the `doit` Python package. It works
like a Makefile, but is Python-based.

End-to-end chain:

    config -> pull_databento -> clean_mbp1 -> run_strategy -> plot_strategy_results

Also includes the entry signal generator task (issue #13), which depends on
clean_mbp1 and runs alongside the strategy chain.

Running plain `doit` executes the whole chain and ends with the strategy PNGs in
_output/figures. The only external requirements are the packages in
requirements.txt and DATABENTO_API_KEY in .env (used once; pulls are cached
under _data/databento and skipped thereafter).

The exploratory notebooks under notebooks/ are research artifacts and are not
part of this chain; they read the parquet files the chain produces.
"""

#######################################
## Configuration and Helpers for PyDoit
#######################################
## Make sure the src folder is in the path
import sys

sys.path.insert(1, "./src/")

from settings import config

from clean_mbp1 import GRID_FREQS, _aligned_path, _events_path, _grid_path
from plot_spread_diagnostics import FIGURE_NAMES as DIAGNOSTIC_FIGURE_NAMES
from plot_strategy_results import FIGURE_NAMES as STRATEGY_FIGURE_NAMES
from pull_databento import (
    OUTRIGHTS,
    PILOT_END,
    PILOT_START,
    SCHEMA,
    SPREADS,
    _cache_path,
)
from signal_generator import signals_path
from strategy_engine import results_path

# Run every action with the same interpreter that is running doit
# (venv-safe on Windows, where bare `python` can resolve elsewhere).
PYTHON = f'"{sys.executable}"'

DOIT_CONFIG = {"backend": "sqlite3", "dep_file": "./.doit-db.sqlite"}

BASE_DIR = config("BASE_DIR")
DATA_DIR = config("DATA_DIR")
OUTPUT_DIR = config("OUTPUT_DIR")


##################################
## Begin PyDoit tasks here
##################################


def task_config():
    """Create empty directories for data and output if they don't exist"""
    return {
        "actions": [f"{PYTHON} ./src/settings.py"],
        "targets": [DATA_DIR, OUTPUT_DIR],
        "file_dep": ["./src/settings.py"],
        "clean": [],
    }


MBP1_CACHE_FILES = [
    _cache_path(symbol, SCHEMA, PILOT_START, PILOT_END)
    for symbol in OUTRIGHTS + SPREADS
]


def task_pull_databento():
    """Pull pilot-week MBP-1 from Databento into the DBN cache (issue #4).

    Requires DATABENTO_API_KEY in .env. Pulls are billable, so already-cached
    symbols are skipped and `doit clean` never deletes the cache.
    """
    return {
        "actions": [f"{PYTHON} ./src/pull_databento.py"],
        "file_dep": ["./src/pull_databento.py"],
        "task_dep": ["config"],
        "targets": MBP1_CACHE_FILES,
        "clean": [],
        "verbosity": 2,
    }


def task_clean_mbp1():
    """Clean/align the MBP-1 pulls into parquet datasets (issue #4)"""
    targets = (
        [_grid_path(s, f) for s in OUTRIGHTS + SPREADS for f in GRID_FREQS]
        + [_events_path(s) for s in SPREADS]
        + [_aligned_path(f) for f in GRID_FREQS]
    )
    return {
        "actions": [f"{PYTHON} ./src/clean_mbp1.py"],
        "file_dep": ["./src/clean_mbp1.py", "./src/pull_databento.py", *MBP1_CACHE_FILES],
        "task_dep": ["pull_databento"],
        "targets": targets,
        "clean": True,
        "verbosity": 2,
    }


def task_spread_diagnostics():
    """Mean-reversion diagnostic figures for the pilot week (issue #4)."""
    return {
        "actions": [f"{PYTHON} ./src/plot_spread_diagnostics.py"],
        "file_dep": [
            "./src/plot_spread_diagnostics.py",
            "./src/clean_mbp1.py",
            _aligned_path("1m"),
        ],
        "task_dep": ["clean_mbp1"],
        "targets": [
            OUTPUT_DIR / "figures" / f"{name}.png"
            for name in DIAGNOSTIC_FIGURE_NAMES
        ],
        "clean": True,
        "verbosity": 2,
    }


def task_run_strategy():
    """Backtest the strategy on the cleaned 1-minute aligned dataset."""
    return {
        "actions": [f"{PYTHON} ./src/strategy_engine.py"],
        "file_dep": [
            "./src/strategy_engine.py",
            "./src/clean_mbp1.py",
            _aligned_path("1m"),
        ],
        "task_dep": ["clean_mbp1"],
        "targets": [results_path()],
        "clean": True,
        "verbosity": 2,
    }


def task_plot_strategy_results():
    """Plot the Brent-WTI strategy backtest results."""
    figure_targets = [
        OUTPUT_DIR / "figures" / f"{name}.png"
        for name in STRATEGY_FIGURE_NAMES
    ]
    return {
        "actions": [f"{PYTHON} ./src/plot_strategy_results.py"],
        "file_dep": [
            "./src/plot_strategy_results.py",
            results_path(),
        ],
        "task_dep": ["run_strategy"],
        "targets": figure_targets,
        "clean": True,
        "verbosity": 2,
    }


def task_signal_generator():
    """Entry signals from rolling z-score of the 1m synthetic spread (issue #13)."""
    return {
        "actions": [f"{PYTHON} ./src/signal_generator.py"],
        "file_dep": [
            "./src/signal_generator.py",
            "./src/clean_mbp1.py",
            _aligned_path("1m"),
        ],
        "task_dep": ["clean_mbp1"],
        "targets": [signals_path()],
        "clean": True,
        "verbosity": 2,
    }
