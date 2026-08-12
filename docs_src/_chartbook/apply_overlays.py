"""Apply project overlays onto the installed chartbook package before a build.

Run from the repo root with the project virtualenv active:

    python docs_src/_chartbook/apply_overlays.py

What it does:
1. Replaces chartbook's pipeline index.md with our emoji-free / no-Pipeline-Specs
   landing template.
2. Strips the repeated "Pipeline Manifest" block from dataframe catalog pages
   (hardcoded in chartbook.markdown_generator).
3. Replaces the dataframe manifest template so empty "Linked Charts" blocks
   are not rendered.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUR_INDEX = Path(__file__).resolve().parent / "index.md"
OUR_DF_MANIFEST = REPO_ROOT / "docs_src" / "_templates" / "dataframe_manifest.md"


def _chartbook_package_dir() -> Path:
    spec = importlib.util.find_spec("chartbook")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("chartbook is not installed in this environment")
    return Path(next(iter(spec.submodule_search_locations)))


def overlay_index(package_dir: Path) -> None:
    dest = package_dir / "docs_src_pipeline" / "index.md"
    dest.write_text(OUR_INDEX.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"overlayed index.md -> {dest}")


def overlay_dataframe_manifest(package_dir: Path) -> None:
    if not OUR_DF_MANIFEST.is_file():
        raise SystemExit(f"missing overlay source: {OUR_DF_MANIFEST}")
    dest = package_dir / "docs_src_pipeline" / "_templates" / "dataframe_manifest.md"
    dest.write_text(OUR_DF_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"overlayed dataframe_manifest.md -> {dest}")


def strip_pipeline_manifest(package_dir: Path) -> None:
    path = package_dir / "markdown_generator.py"
    text = path.read_text(encoding="utf-8")
    if "pipeline_manifest.md" not in text:
        print(f"pipeline manifest already stripped in {path}")
        return

    # Match the trailing Pipeline Manifest section ChartBook appends to every
    # dataframe page, including the blank lines around it.
    pattern = re.compile(
        r"\n## Pipeline Manifest\n\n\{\% include \"pipeline_manifest\.md\" \%\}\n",
    )
    new_text, n = pattern.subn("\n", text, count=1)
    if n != 1:
        raise SystemExit(
            f"expected to strip one Pipeline Manifest block from {path}, found {n}"
        )
    path.write_text(new_text, encoding="utf-8")
    print(f"stripped Pipeline Manifest block from {path}")


def main() -> None:
    if not OUR_INDEX.is_file():
        raise SystemExit(f"missing overlay source: {OUR_INDEX}")
    package_dir = _chartbook_package_dir()
    overlay_index(package_dir)
    overlay_dataframe_manifest(package_dir)
    strip_pipeline_manifest(package_dir)


if __name__ == "__main__":
    # Allow running from any cwd.
    sys.path.insert(0, str(REPO_ROOT))
    main()
