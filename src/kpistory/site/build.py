"""Generate every MkDocs page from the processed data and the catalog."""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import plotly

from ..data.pipeline import load_tables
from ..engine import Engine
from ..paths import DOCS_DIR
from . import catalog_pages
from .current import current_values
from .data_sources import page as data_sources_page

CASES = ["service", "maintenance", "inventory", "customers", "data_quality"]


def _copy_plotly_js() -> None:
    src = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    dst = DOCS_DIR / "assets" / "js" / "plotly.min.js"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def build() -> None:
    tables, manifest = load_tables()
    engine = Engine()
    _copy_plotly_js()
    cases_dir = DOCS_DIR / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    built: set[str] = set()
    for case in CASES:
        try:
            module = importlib.import_module(f".case_{case}", __package__)
        except ModuleNotFoundError:
            continue
        (cases_dir / f"{case}.md").write_text(
            module.build(tables, engine, manifest), encoding="utf-8"
        )
        built.add(case)
        print(f"  page cases/{case}.md")
    try:
        antipatterns = importlib.import_module(".antipatterns", __package__)
        (DOCS_DIR / "antipatterns.md").write_text(
            antipatterns.build(tables, engine), encoding="utf-8"
        )
        print("  page antipatterns.md")
    except ModuleNotFoundError:
        pass
    catalog_pages.write(engine, current_values(tables, engine), DOCS_DIR / "catalog", built)
    (DOCS_DIR / "data-sources.md").write_text(data_sources_page(manifest), encoding="utf-8")
    print(f"  catalog pages: {len(engine.catalog) + 1}; data-sources.md")
