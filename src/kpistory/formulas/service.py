"""Service operations & SLA KPIs (table: tickets)."""

from __future__ import annotations

import pandas as pd

from . import kpi, median_or_nan, safe_ratio


def derive_ticket_columns(tickets: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    """Add the measured columns every service KPI uses. Computed once, here.

    first_response_hours, resolution_hours: elapsed calendar hours.
    age_days: age of open tickets at the snapshot (NaN for resolved tickets).
    within_sla: resolution_hours <= sla_target_hours (NaN for open tickets).
    """
    df = tickets.copy()
    df["first_response_hours"] = (
        df["first_response_at"] - df["created_at"]
    ).dt.total_seconds() / 3600
    df["resolution_hours"] = (df["resolved_at"] - df["created_at"]).dt.total_seconds() / 3600
    is_open = df["status"].eq("open")
    df["age_days"] = ((snapshot - df["created_at"]).dt.total_seconds() / 86400).where(is_open)
    df["within_sla"] = (df["resolution_hours"] <= df["sla_target_hours"]).where(~is_open)
    return df


def _resolved(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["status"].eq("resolved")]


@kpi("first_response_time")
def first_response_time(df: pd.DataFrame) -> float:
    return median_or_nan(df["first_response_hours"])


@kpi("resolution_time")
def resolution_time(df: pd.DataFrame) -> float:
    return median_or_nan(_resolved(df)["resolution_hours"])


@kpi("sla_compliance")
def sla_compliance(df: pd.DataFrame) -> float:
    r = _resolved(df)
    return safe_ratio((r["resolution_hours"] <= r["sla_target_hours"]).sum(), len(r))


@kpi("backlog_aged_share")
def backlog_aged_share(df: pd.DataFrame, age_limit_days: float) -> float:
    open_ = df[df["status"].eq("open")]
    return safe_ratio((open_["age_days"] > age_limit_days).sum(), len(open_))


@kpi("first_contact_resolution")
def first_contact_resolution(df: pd.DataFrame) -> float:
    r = _resolved(df)
    return safe_ratio((r["contacts"].eq(1) & ~r["reopened"].astype(bool)).sum(), len(r))


@kpi("reopen_rate")
def reopen_rate(df: pd.DataFrame) -> float:
    r = _resolved(df)
    return safe_ratio(r["reopened"].astype(bool).sum(), len(r))
