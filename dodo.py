"""Run or update the project. This file uses the `doit` Python package. It works
like a Makefile, but is Python-based.

Minimal end-to-end chain (issue #38):

    config -> pull_databento -> clean_mbp1 -> random_strategy -> random_strategy_plots

Running plain `doit` executes the whole chain and ends with sample PNGs in
_output/figures. The only external requirements are the packages in
requirements.txt and DATABENTO_API_KEY in .env (used once; pulls are cached
under _data/databento and skipped thereafter).

Task definitions removed in the issue #38 slim-down (LaTeX, example tables,
notebooks, chartbook site, pytest) live in git history and can be re-added
incrementally.
"""

#######################################
## Configuration and Helpers for PyDoit
#######################################
## Make sure the src folder is in the path
import sys

sys.path.insert(1, "./src/")

from settings import config

from clean_mbp1 import GRID_FREQS, _aligned_path, _events_path, _grid_path
from plot_random_strategy import FIGURE_NAMES
from pull_databento import (
    OUTRIGHTS,
    PILOT_END,
    PILOT_START,
    SCHEMA,
    SPREADS,
    _cache_path,
)
from random_strategy import result_path as strategy_result_path

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


def task_random_strategy():
    """Placeholder random die-roll strategy on the front listed spread (issue #38)"""
    return {
        "actions": [f"{PYTHON} ./src/random_strategy.py"],
        "file_dep": [
            "./src/random_strategy.py",
            "./src/clean_mbp1.py",
            _grid_path(SPREADS[0], "1m"),
        ],
        "task_dep": ["clean_mbp1"],
        "targets": [strategy_result_path()],
        "clean": True,
        "verbosity": 2,
    }


def task_random_strategy_plots():
    """Sample plots (price/trades, position, cumulative PnL) for issue #38"""
    return {
        "actions": [f"{PYTHON} ./src/plot_random_strategy.py"],
        "file_dep": [
            "./src/plot_random_strategy.py",
            "./src/random_strategy.py",
            strategy_result_path(),
        ],
        "task_dep": ["random_strategy"],
        "targets": [OUTPUT_DIR / "figures" / f"{name}.png" for name in FIGURE_NAMES],
        "clean": True,
        "verbosity": 2,
    }
