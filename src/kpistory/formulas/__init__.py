"""KPI formulas: exactly one Python function per catalog KPI.

Each function receives a pandas DataFrame shaped as declared in the catalog
(`input.table`, `input.columns`) plus the KPI's `params`, and returns a float
(NaN when the KPI is undefined, e.g. an empty denominator). Functions never
hard-code targets, thresholds or parameters: those live in kpis/catalog.yaml.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

KpiFunc = Callable[..., float]
REGISTRY: dict[str, KpiFunc] = {}


def kpi(kpi_id: str) -> Callable[[KpiFunc], KpiFunc]:
    """Register a function as the single implementation of a catalog KPI."""

    def decorator(func: KpiFunc) -> KpiFunc:
        if kpi_id in REGISTRY:
            raise ValueError(f"KPI '{kpi_id}' is implemented twice")
        REGISTRY[kpi_id] = func
        func.kpi_id = kpi_id  # type: ignore[attr-defined]
        return func

    return decorator


def safe_ratio(numerator: float, denominator: float) -> float:
    """numerator / denominator, NaN when the denominator is zero (a zero denominator means 'undefined', not 0)."""
    return float(numerator) / float(denominator) if denominator else float("nan")


def median_or_nan(series: pd.Series) -> float:
    series = series.dropna()
    return float(series.median()) if len(series) else float("nan")


# Import modules so their @kpi decorators run.
from . import customers, data_quality, inventory, maintenance, sectores, service  # noqa: E402,F401
