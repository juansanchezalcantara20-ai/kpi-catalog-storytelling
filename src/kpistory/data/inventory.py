"""Case 3 data: a synthetic stock simulation driven by public demand.

Online Retail II tells us what customers ordered, not what stock the retailer held.
This module simulates the missing half with an explicit, documented policy:

* SKUs: the 40 best sellers by units plus 8 "faded" SKUs (good sellers whose demand
  stopped at least 200 days before the end of the log) - the obsolescence candidates.
* Forecast: 8-week moving average of weekly demand, made at the end of the previous week.
  This is a deliberately common baseline; its lag around the Q4 gift season is the story.
* Replenishment: weekly review, order-up-to level = 5 weeks of forecast,
  supplier lead time 10-17 days. Demand not served from stock is lost (no backorders).
* Delivery: promised 3 days after the order; carrier transit 1-4 days, slower in Nov-Dec.
* Unit cost = 60% of the median selling price of the SKU.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 31
N_TOP, N_FADED = 40, 8
MA_WEEKS = 8
ORDER_UP_TO_WEEKS = 5.0
PROMISE_DAYS = 3


def select_skus(sales: pd.DataFrame, end: pd.Timestamp) -> list[str]:
    units = sales.groupby("sku")["quantity"].sum().sort_values(ascending=False)
    top = list(units.index[:N_TOP])
    last_sale = sales.groupby("sku")["invoice_date"].max()
    faded = units[
        (last_sale.reindex(units.index) < end - pd.Timedelta(days=200)) & ~units.index.isin(top)
    ]
    return top + list(faded.index[:N_FADED])


def weekly_forecast(daily_demand: pd.DataFrame) -> pd.DataFrame:
    """Moving-average forecast per SKU and week (week starts Monday)."""
    weekly = (
        daily_demand.assign(week=daily_demand["date"].dt.to_period("W-SUN").dt.start_time)
        .groupby(["sku", "week"])["demand_units"]
        .sum()
        .rename("actual_units")
        .reset_index()
    )
    weekly["forecast_units"] = weekly.groupby("sku")["actual_units"].transform(
        lambda s: s.shift(1).rolling(MA_WEEKS, min_periods=4).mean()
    )
    # Only complete weeks: a partial last week would look like a demand collapse.
    first, last = daily_demand["date"].min(), daily_demand["date"].max()
    complete = (weekly["week"] >= first) & (weekly["week"] + pd.Timedelta(days=6) <= last)
    return weekly[complete].dropna(subset=["forecast_units"]).reset_index(drop=True)


def simulate(sales: pd.DataFrame, seed: int = SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    start, end = sales["invoice_date"].min().normalize(), sales["invoice_date"].max().normalize()
    skus = select_skus(sales, end)
    lines = sales[sales["sku"].isin(skus)].copy()
    lines["date"] = lines["invoice_date"].dt.normalize()
    days = pd.date_range(start, end, freq="D")
    demand = (
        lines.groupby(["sku", "date"])["quantity"]
        .sum()
        .unstack("sku")
        .reindex(index=days, columns=skus)
        .fillna(0)
    )
    unit_cost = (lines.groupby("sku")["unit_price"].median() * 0.6).reindex(skus)

    # Forecast available at each Monday = mean of the previous 8 complete weeks.
    weekly = demand.resample("W-SUN").sum()
    fc_weekly = weekly.shift(1).rolling(MA_WEEKS, min_periods=1).mean().bfill()

    on_hand = (weekly.iloc[:4].mean() * 4).round().to_numpy()
    pipeline: list[tuple[int, np.ndarray]] = []  # (arrival day index, quantities)
    rec_on_hand = np.zeros((len(days), len(skus)))
    rec_shipped = np.zeros((len(days), len(skus)))
    for i, day in enumerate(days):
        arriving = [q for d, q in pipeline if d == i]
        pipeline = [(d, q) for d, q in pipeline if d != i]
        for q in arriving:
            on_hand += q
        if day.dayofweek == 0:  # weekly review on Mondays
            week_fc = fc_weekly.loc[fc_weekly.index >= day].iloc[0].to_numpy()
            position = on_hand + sum((q for _, q in pipeline), np.zeros(len(skus)))
            qty = np.maximum(0, np.round(week_fc * ORDER_UP_TO_WEEKS - position))
            if qty.any():
                pipeline.append((i + int(rng.integers(10, 18)), qty))
        d = demand.iloc[i].to_numpy()
        shipped = np.minimum(on_hand, d)
        on_hand = on_hand - shipped
        rec_on_hand[i], rec_shipped[i] = on_hand, shipped

    idx = pd.MultiIndex.from_product([days, skus], names=["date", "sku"])
    daily = pd.DataFrame(
        {
            "on_hand_units": rec_on_hand.ravel(),
            "demand_units": demand.to_numpy().ravel(),
            "shipped_units": rec_shipped.ravel(),
        },
        index=idx,
    ).reset_index()
    first_d = daily[daily["demand_units"] > 0].groupby("sku")["date"].min()
    last_d = daily[daily["demand_units"] > 0].groupby("sku")["date"].max()
    daily["active"] = (daily["date"] >= daily["sku"].map(first_d)) & (
        daily["date"] <= daily["sku"].map(last_d)
    )
    daily["unit_cost"] = daily["sku"].map(unit_cost)
    daily["on_hand_value"] = daily["on_hand_units"] * daily["unit_cost"]
    daily["cogs_value"] = daily["shipped_units"] * daily["unit_cost"]

    # Allocate each day's shipped units to that day's order lines, first come first served.
    shipped_map = daily.set_index(["date", "sku"])["shipped_units"]
    lines = lines.sort_values("invoice_date")
    lines["cum"] = lines.groupby(["sku", "date"])["quantity"].cumsum()
    avail = shipped_map.reindex(pd.MultiIndex.from_arrays([lines["date"], lines["sku"]])).to_numpy()
    lines["qty_shipped"] = np.clip(
        avail - (lines["cum"] - lines["quantity"]), 0, lines["quantity"]
    ).astype(int)
    peak = lines["date"].dt.month.isin([11, 12]).to_numpy()
    transit = rng.choice([1, 2, 3, 4], size=len(lines), p=[0.40, 0.42, 0.15, 0.03])
    transit = np.where(
        peak & (rng.random(len(lines)) < 0.15), rng.integers(4, 7, len(lines)), transit
    )
    order_lines = pd.DataFrame(
        {
            "order_id": lines["invoice_id"],
            "sku": lines["sku"],
            "customer_id": lines["customer_id"],
            "order_date": lines["date"],
            "promised_date": lines["date"] + pd.Timedelta(days=PROMISE_DAYS),
            "delivered_date": lines["date"] + pd.to_timedelta(transit, unit="D"),
            "qty_ordered": lines["quantity"].astype(int),
            "qty_shipped": lines["qty_shipped"],
        }
    )
    # A transit delay applies per order (one parcel), not per line.
    first = order_lines.groupby("order_id")["delivered_date"].transform("max")
    order_lines["delivered_date"] = first

    last_move = (
        daily[daily["shipped_units"] > 0].groupby("sku")["date"].max().reindex(skus).fillna(start)
    )
    snap = daily[daily["date"].eq(end)].set_index("sku")
    snapshot = pd.DataFrame(
        {
            "sku": skus,
            "on_hand_units": snap["on_hand_units"].reindex(skus).to_numpy(),
            "on_hand_value": snap["on_hand_value"].reindex(skus).to_numpy(),
            "days_since_last_movement": (end - last_move).dt.days.to_numpy(),
            "sku_group": ["Best seller"] * min(N_TOP, len(skus))
            + ["Faded"] * max(0, len(skus) - N_TOP),
        }
    )
    forecast = weekly_forecast(daily[["sku", "date", "demand_units"]])
    return {
        "order_lines": order_lines.reset_index(drop=True),
        "inventory_daily": daily,
        "inventory_snapshot": snapshot,
        "forecast": forecast,
    }
