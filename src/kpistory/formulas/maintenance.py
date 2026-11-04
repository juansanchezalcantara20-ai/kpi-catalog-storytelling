"""Maintenance & reliability KPIs (tables: work_orders, asset_periods)."""

from __future__ import annotations

import pandas as pd

from . import kpi, safe_ratio


def pm_on_time(work_orders: pd.DataFrame, tolerance_days: float) -> pd.Series:
    """True when a work order was completed no later than due_date + tolerance."""
    deadline = work_orders["due_date"] + pd.to_timedelta(tolerance_days, unit="D")
    return work_orders["completed_at"].notna() & (work_orders["completed_at"] <= deadline)


@kpi("mtbf")
def mtbf(df: pd.DataFrame) -> float:
    return safe_ratio(df["operating_hours"].sum(), df["failures"].sum())


@kpi("mttr")
def mttr(df: pd.DataFrame) -> float:
    repairs = df.loc[df["wo_type"].eq("corrective"), "repair_hours"].dropna()
    return float(repairs.mean()) if len(repairs) else float("nan")


@kpi("availability")
def availability(df: pd.DataFrame) -> float:
    scheduled = df["scheduled_hours"].sum()
    return safe_ratio(scheduled - df["unplanned_downtime_hours"].sum(), scheduled)


@kpi("pm_compliance")
def pm_compliance(df: pd.DataFrame, tolerance_days: float) -> float:
    pm = df[df["wo_type"].eq("preventive")]
    return safe_ratio(pm_on_time(pm, tolerance_days).sum(), len(pm))


@kpi("planned_work_share")
def planned_work_share(df: pd.DataFrame) -> float:
    planned = df.loc[df["planned"].astype(bool), "labor_hours"].sum()
    return safe_ratio(planned, df["labor_hours"].sum())
