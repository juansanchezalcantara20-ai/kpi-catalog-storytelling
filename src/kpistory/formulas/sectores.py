"""Sector KPIs (tables: creditos, energia_anual, salud_semanal, moviles_anual, docentes, vuelos)."""

from __future__ import annotations

import pandas as pd

from . import kpi, median_or_nan, safe_ratio


@kpi("npl_ratio")
def npl_ratio(df: pd.DataFrame) -> float:
    return safe_ratio(df["overdue_balance"].sum(), df["loan_balance"].sum())


@kpi("renewable_share_elec")
def renewable_share_elec(df: pd.DataFrame) -> float:
    return safe_ratio(df["renewables_twh"].sum(), df["generation_twh"].sum())


@kpi("fossil_share_elec")
def fossil_share_elec(df: pd.DataFrame) -> float:
    return safe_ratio(df["fossil_twh"].sum(), df["generation_twh"].sum())


@kpi("carbon_intensity_elec")
def carbon_intensity_elec(df: pd.DataFrame) -> float:
    d = df.dropna(subset=["carbon_intensity", "generation_twh"])
    return safe_ratio(
        (d["carbon_intensity"] * d["generation_twh"]).sum(), d["generation_twh"].sum()
    )


@kpi("vaccination_complete_share")
def vaccination_complete_share(df: pd.DataFrame) -> float:
    d = df.dropna(subset=["fully_vaccinated", "population"])
    last = d.sort_values("week").groupby("country").tail(1)
    return safe_ratio(last["fully_vaccinated"].sum(), last["population"].sum())


@kpi("deaths_per_million_week")
def deaths_per_million_week(df: pd.DataFrame) -> float:
    d = df.dropna(subset=["deaths", "population"])
    return safe_ratio(d["deaths"].sum() * 1_000_000, d["population"].sum())


@kpi("mobile_penetration")
def mobile_penetration(df: pd.DataFrame) -> float:
    d = df.dropna(subset=["lines", "population"])
    return safe_ratio(d["lines"].sum() * 100, d["population"].sum())


@kpi("pupil_teacher_ratio")
def pupil_teacher_ratio(df: pd.DataFrame) -> float:
    return median_or_nan(df["student_ratio"])


@kpi("on_time_share")
def on_time_share(df: pd.DataFrame, tolerance_minutes: float) -> float:
    d = df["delay_minutes"].dropna()
    return safe_ratio((d <= tolerance_minutes).sum(), len(d))


@kpi("loan_growth")
def loan_growth(df: pd.DataFrame) -> float:
    by = df.groupby("month")["loan_balance"].sum().sort_index()
    last = by.index.max()
    before = last - pd.DateOffset(months=12)
    return (
        safe_ratio(by.get(last, 0.0), by.get(before, 0.0)) - 1
        if before in by.index
        else float("nan")
    )


@kpi("lines_growth")
def lines_growth(df: pd.DataFrame) -> float:
    by = df.groupby("year")["lines"].sum().sort_index()
    if len(by) < 2 or by.index[-1] - 1 not in by.index:
        return float("nan")
    return safe_ratio(by.iloc[-1], by.loc[by.index[-1] - 1]) - 1
