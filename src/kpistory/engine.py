"""Calculation engine: computes any catalog KPI, grouped or not, and grades it.

The engine is the only entry point the story site and the dashboard use, so
a KPI is computed in exactly one way everywhere.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from . import catalog as catalog_mod
from .catalog import KPI, Catalog
from .formulas import REGISTRY

STATUS_LABEL = {"green": "En meta", "amber": "Vigilar", "red": "Actuar", "n/a": "Sin dato"}


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


UNIT_SUFFIX = {
    "hours": " h", "days": " días", "times_per_year": " veces al año", "score": "",
    "g_per_kwh": " g por kWh", "per_million": " por millón", "per_100": " por cada 100", "ratio": " alumnos por docente",
}  # fmt: skip


def number(value: float, decimals: int = 0) -> str:
    """Spanish-style number for this site: decimal point, space as thousands separator."""
    return f"{value:,.{decimals}f}".replace(",", " ")


def pct(value: float, decimals: int = 1) -> str:
    """0.892 -> '89.2 %' (space before %)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "sin dato"
    return f"{number(value * 100, decimals)} %"


def format_value(k: KPI, value: float, decimals: int | None = None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "sin dato"
    d = 1 if decimals is None else decimals
    if k.unit == "percent":
        return pct(value, d)
    if k.unit == "score":
        return f"{value:+.0f}"
    return f"{number(value, d)}{UNIT_SUFFIX[k.unit]}"


def format_threshold(k: KPI, with_alert: bool = True) -> str:
    """Target rule in words, e.g. '≥ 90.0 % (vigilar desde 85.0 %)'."""

    def f(v: float) -> str:
        return format_value(k, v)

    g, a = k.thresholds["green"], k.thresholds["amber"]
    if k.direction == "higher_is_better":
        main, alert = f"≥ {f(g)}", f"vigilar desde {f(a)}"
    elif k.direction == "lower_is_better":
        main, alert = f"≤ {f(g)}", f"vigilar hasta {f(a)}"
    else:
        main, alert = f"entre {f(g[0])} y {f(g[1])}", f"vigilar entre {f(a[0])} y {f(a[1])}"
    return f"{main} ({alert})" if with_alert else main
