"""Inventory & demand KPIs (tables: order_lines, inventory_daily, inventory_snapshot, forecast)."""

from __future__ import annotations

import pandas as pd

from . import kpi, safe_ratio


@kpi("fill_rate")
def fill_rate(df: pd.DataFrame) -> float:
    return safe_ratio(df["qty_shipped"].sum(), df["qty_ordered"].sum())


@kpi("otif")
def otif(df: pd.DataFrame) -> float:
    line_ok = (
        (df["qty_shipped"] >= df["qty_ordered"])
        & df["delivered_date"].notna()
        & (df["delivered_date"] <= df["promised_date"])
    )
    order_ok = line_ok.groupby(df["order_id"]).all()
    return safe_ratio(order_ok.sum(), len(order_ok))


@kpi("inventory_turnover")
def inventory_turnover(df: pd.DataFrame) -> float:
    days = df["date"].nunique()
    if not days:
        return float("nan")
    avg_inventory = df.groupby("date")["on_hand_value"].sum().mean()
    return safe_ratio(df["cogs_value"].sum() * 365 / days, avg_inventory)


@kpi("days_of_cover")
def days_of_cover(df: pd.DataFrame) -> float:
    days = df["date"].nunique()
    if not days:
        return float("nan")
    on_hand_last = df.loc[df["date"].eq(df["date"].max()), "on_hand_units"].sum()
    return safe_ratio(on_hand_last, df["demand_units"].sum() / days)


@kpi("stockout_rate")
def stockout_rate(df: pd.DataFrame) -> float:
    active = df[df["active"].astype(bool)]
    return safe_ratio((active["on_hand_units"] <= 0).sum(), len(active))


@kpi("obsolescence_share")
def obsolescence_share(df: pd.DataFrame, age_limit_days: float) -> float:
    old = df.loc[df["days_since_last_movement"] > age_limit_days, "on_hand_value"].sum()
    return safe_ratio(old, df["on_hand_value"].sum())


@kpi("mape")
def mape(df: pd.DataFrame) -> float:
    d = df[df["actual_units"] > 0]
    if d.empty:
        return float("nan")
    return float(((d["actual_units"] - d["forecast_units"]).abs() / d["actual_units"]).mean())


@kpi("wape")
def wape(df: pd.DataFrame) -> float:
    return safe_ratio(
        (df["actual_units"] - df["forecast_units"]).abs().sum(), df["actual_units"].sum()
    )


@kpi("forecast_bias")
def forecast_bias(df: pd.DataFrame) -> float:
    actual = df["actual_units"].sum()
    return safe_ratio(df["forecast_units"].sum() - actual, actual)
