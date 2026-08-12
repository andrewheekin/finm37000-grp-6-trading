"""Draw the project logo and favicon.

Writes assets/logo.png (sidebar lockup) and assets/favicon.ico (square mark).
Colors match the figure palette in plot_strategy_results.py.

Usage:
    python src/make_logo.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch
from PIL import Image

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
SERIES = "#2a78d6"
MEAN = "#d38b1f"
MAROON = "#800000"


def _spread_curve(n: int = 40, seed: int = 11) -> np.ndarray:
    """A mean-reverting path: AR(1) pulled back toward zero.

    Kept deliberately short. At sidebar size a dense series reads as noise
    rather than as a series crossing its mean.
    """
    rng = np.random.default_rng(seed)
    phi, x = 0.62, 0.0
    out = []
    for _ in range(n):
        x = phi * x + rng.normal(0, 0.55)
        out.append(x)
    y = np.array(out)
    y = y - y.mean()
    return y / np.abs(y).max()


def _draw_mark(ax) -> None:
    """The square tile: spread oscillating around its dashed rolling mean."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.add_patch(
        FancyBboxPatch(
            (0.035, 0.035),
            0.93,
            0.93,
            boxstyle="round,pad=0,rounding_size=0.16",
            linewidth=3.0,
            edgecolor=MAROON,
            facecolor=SURFACE,
            mutation_aspect=1,
        )
    )

    y = _spread_curve()
    x = np.linspace(0.14, 0.86, y.size)
    y = 0.5 + 0.28 * y

    ax.plot([0.14, 0.86], [0.5, 0.5], color=MEAN, lw=2.6, ls=(0, (3, 2.4)), zorder=2)
    ax.plot(x, y, color=SERIES, lw=2.9, solid_joinstyle="round", zorder=3)


def build_logo(scale: int = 3) -> Path:
    """Horizontal lockup: mark plus wordmark, for the site sidebar."""
    fig = plt.figure(figsize=(4.6, 1.35), dpi=100 * scale)
    fig.patch.set_alpha(0)

    ax_mark = fig.add_axes([0.005, 0.04, 0.29, 0.92])
    _draw_mark(ax_mark)

    ax_text = fig.add_axes([0.33, 0.0, 0.67, 1.0])
    ax_text.set_xlim(0, 1)
    ax_text.set_ylim(0, 1)
    ax_text.axis("off")

    ax_text.text(
        0, 0.60, "FINM 37000", color=MAROON, fontsize=25, fontweight="bold", va="center"
    )
    ax_text.text(0, 0.28, "G R O U P  6", color=INK, fontsize=13, va="center")
    ax_text.plot([0.005, 0.52], [0.45, 0.45], color=GRID, lw=1.6)

    path = ASSETS_DIR / "logo.png"
    fig.savefig(path, transparent=True)
    plt.close(fig)
    return path


def build_favicon() -> Path:
    """Square mark only, written as a real multi-size .ico."""
    fig = plt.figure(figsize=(1, 1), dpi=256)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    _draw_mark(ax)

    png = ASSETS_DIR / "favicon.png"
    fig.savefig(png, transparent=True)
    plt.close(fig)

    ico = ASSETS_DIR / "favicon.ico"
    Image.open(png).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    png.unlink()
    return ico


def main() -> None:
    ASSETS_DIR.mkdir(exist_ok=True)
    for path in (build_logo(), build_favicon()):
        print(f"saved {path} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
