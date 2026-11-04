"""Data quality KPIs. They apply to any table; the rules per dataset live in kpis/dq_rules.yaml."""

from __future__ import annotations

import pandas as pd

from . import kpi, safe_ratio


def completeness_counts(df: pd.DataFrame, columns: list[str]) -> tuple[int, int]:
    """(non-null required cells, required cells). Empty strings count as missing."""
    cells = df[columns].replace(r"^\s*$", pd.NA, regex=True)
    return int(cells.notna().sum().sum()), int(cells.size)


def uniqueness_counts(df: pd.DataFrame, key: list[str]) -> tuple[int, int]:
    return int(len(df.drop_duplicates(subset=key))), int(len(df))


def validity_mask(df: pd.DataFrame, rules: list[str]) -> pd.Series:
    """True for rows passing every rule (pandas eval expressions); NaN results fail."""
    ok = pd.Series(True, index=df.index)
    for rule in rules:
        ok &= df.eval(rule).fillna(False).astype(bool)
    return ok


def timeliness_counts(
    df: pd.DataFrame, event_col: str, loaded_col: str, max_delay_hours: float
) -> tuple[int, int]:
    delay = (df[loaded_col] - df[event_col]).dt.total_seconds() / 3600
    return int((delay <= max_delay_hours).sum()), int(len(df))


@kpi("dq_completeness")
def dq_completeness(df: pd.DataFrame, columns: list[str]) -> float:
    return safe_ratio(*completeness_counts(df, columns))


@kpi("dq_uniqueness")
def dq_uniqueness(df: pd.DataFrame, key: list[str]) -> float:
    return safe_ratio(*uniqueness_counts(df, key))


@kpi("dq_validity")
def dq_validity(df: pd.DataFrame, rules: list[str]) -> float:
    return safe_ratio(validity_mask(df, rules).sum(), len(df))


@kpi("dq_timeliness")
def dq_timeliness(
    df: pd.DataFrame, event_col: str, loaded_col: str, max_delay_hours: float
) -> float:
    return safe_ratio(*timeliness_counts(df, event_col, loaded_col, max_delay_hours))
