"""Calculation engine: computes any catalog KPI, grouped or not, and grades it.

The engine is the only entry point the site and the Power BI exporter use, so
a KPI is computed in exactly one way everywhere.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from . import catalog as catalog_mod
from .catalog import KPI, Catalog
from .formulas import REGISTRY

STATUS_LABEL = {"green": "On target", "amber": "Watch", "red": "Act", "n/a": "No data"}


class Engine:
    def __init__(self, catalog: Catalog | None = None):
        self.catalog = catalog or catalog_mod.load()

    # ------------------------------------------------------------------ compute
    def compute(self, kpi_id: str, df: pd.DataFrame, **overrides: Any) -> float:
        """Compute one KPI on a table. `overrides` replace catalog params (DQ rules, tests)."""
        k = self.catalog[kpi_id]
        missing = [c for c in k.input["columns"] if c not in df.columns]
        if missing:
            raise KeyError(f"{kpi_id}: input table is missing columns {missing}")
        params = {**k.params, **overrides}
        return float(REGISTRY[kpi_id](df, **params))

    def compute_by(
        self, kpi_id: str, df: pd.DataFrame, by: str | list[str], **overrides: Any
    ) -> pd.DataFrame:
        """Compute a KPI per group. Returns columns: <by>, value, status."""
        rows = []
        for key, group in df.groupby(by, observed=True, sort=True):
            value = self.compute(kpi_id, group, **overrides)
            keys = key if isinstance(key, tuple) else (key,)
            by_cols = [by] if isinstance(by, str) else list(by)
            rows.append(
                {
                    **dict(zip(by_cols, keys, strict=True)),
                    "value": value,
                    "status": self.status(kpi_id, value),
                }
            )
        return pd.DataFrame(rows)

    # -------------------------------------------------------------------- grade
    def status(self, kpi_id: str, value: float) -> str:
        """Traffic-light status from the catalog thresholds and direction."""
        return grade(self.catalog[kpi_id], value)

    def format(self, kpi_id: str, value: float) -> str:
        return format_value(self.catalog[kpi_id], value)


def grade(k: KPI, value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    green, amber = k.thresholds["green"], k.thresholds["amber"]
    if k.direction == "higher_is_better":
        return "green" if value >= green else "amber" if value >= amber else "red"
    if k.direction == "lower_is_better":
        return "green" if value <= green else "amber" if value <= amber else "red"
    in_green = green[0] <= value <= green[1]
    in_amber = amber[0] <= value <= amber[1]
    return "green" if in_green else "amber" if in_amber else "red"


def format_value(k: KPI, value: float, decimals: int | None = None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    if k.unit == "percent":
        d = 1 if decimals is None else decimals
        return f"{value * 100:.{d}f}%"
    suffix = {"hours": " h", "days": " days", "times_per_year": "x / year", "score": ""}[k.unit]
    d = 1 if decimals is None else decimals
    if k.unit == "score":
        return f"{value:+.0f}"
    return f"{value:,.{d}f}{suffix}"


def format_threshold(k: KPI) -> str:
    """Human-readable target rule, e.g. '>= 90.0% (amber >= 85.0%)'."""

    def f(v: float) -> str:
        return format_value(k, v)

    g, a = k.thresholds["green"], k.thresholds["amber"]
    if k.direction == "higher_is_better":
        return f"≥ {f(g)} (amber ≥ {f(a)})"
    if k.direction == "lower_is_better":
        return f"≤ {f(g)} (amber ≤ {f(a)})"
    return f"{f(g[0])} to {f(g[1])} (amber {f(a[0])} to {f(a[1])})"
