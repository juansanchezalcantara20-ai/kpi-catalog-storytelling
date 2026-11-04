"""Customer KPIs (tables: sales, customer_rfm, survey)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import kpi, safe_ratio

PANDAS_PERIOD = {"MONTH": "M", "QUARTER": "Q", "YEAR": "Y"}

# RFM segment rules on 1-5 scores (5 = best). Evaluated top to bottom; first match wins.
RFM_SEGMENTS: list[tuple[str, str]] = [
    ("Champions", "r >= 4 and f >= 4"),
    ("Loyal", "r >= 3 and f >= 3"),
    ("At risk", "r <= 2 and f >= 3"),
    ("New / promising", "r >= 4 and f <= 2"),
    ("Hibernating", "r <= 2 and f <= 2"),
    ("Needs attention", "True"),
]


def _quintile_score(values: pd.Series, ascending: bool) -> pd.Series:
    """1-5 score by quintile of rank (ties broken by order, robust to heavy ties)."""
    ranks = values.rank(method="first", ascending=ascending)
    return np.ceil(ranks / len(values) * 5).clip(1, 5).astype(int)


def rfm_table(sales: pd.DataFrame, snapshot: pd.Timestamp, window_days: int = 365) -> pd.DataFrame:
    """Recency / frequency / monetary per customer over the look-back window, with segment."""
    window = sales[
        (sales["invoice_date"] > snapshot - pd.Timedelta(days=window_days))
        & (sales["invoice_date"] <= snapshot)
    ]
    g = window.groupby("customer_id")
    rfm = pd.DataFrame(
        {
            "recency_days": (snapshot - g["invoice_date"].max()).dt.days,
            "frequency": g["invoice_id"].nunique(),
            "monetary": g["revenue"].sum(),
        }
    ).reset_index()
    rfm["r"] = _quintile_score(rfm["recency_days"], ascending=False)  # recent = high score
    rfm["f"] = _quintile_score(rfm["frequency"], ascending=True)
    rfm["m"] = _quintile_score(rfm["monetary"], ascending=True)
    rfm["segment"] = "Needs attention"
    assigned = pd.Series(False, index=rfm.index)
    for name, rule in RFM_SEGMENTS:
        mask = rfm.eval(rule) & ~assigned if rule != "True" else ~assigned
        rfm.loc[mask, "segment"] = name
        assigned |= mask
    return rfm


@kpi("retention_rate")
def retention_rate(df: pd.DataFrame, period: str) -> float:
    """Retention between the last two periods present in `df`."""
    periods = df["invoice_date"].dt.to_period(PANDAS_PERIOD[period])
    present = sorted(periods.unique())
    if len(present) < 2:
        return float("nan")
    prev, curr = present[-2], present[-1]
    prev_customers = set(df.loc[periods.eq(prev), "customer_id"])
    curr_customers = set(df.loc[periods.eq(curr), "customer_id"])
    return safe_ratio(len(prev_customers & curr_customers), len(prev_customers))


def retention_series(df: pd.DataFrame, period: str) -> pd.Series:
    """Retention for every consecutive pair of periods (helper for trend charts)."""
    periods = df["invoice_date"].dt.to_period(PANDAS_PERIOD[period])
    out = {}
    present = sorted(periods.unique())
    for prev, curr in zip(present, present[1:], strict=False):
        sub = df[periods.isin([prev, curr])]
        out[str(curr)] = retention_rate(sub, period)
    return pd.Series(out, dtype=float)


@kpi("repeat_purchase_rate")
def repeat_purchase_rate(df: pd.DataFrame) -> float:
    orders = df.groupby("customer_id")["invoice_id"].nunique()
    return safe_ratio((orders >= 2).sum(), len(orders))


@kpi("revenue_at_risk_share")
def revenue_at_risk_share(df: pd.DataFrame) -> float:
    at_risk = df.loc[df["segment"].eq("At risk"), "monetary"].sum()
    return safe_ratio(at_risk, df["monetary"].sum())


@kpi("nps")
def nps(df: pd.DataFrame) -> float:
    scores = df["score"].dropna()
    if scores.empty:
        return float("nan")
    return 100 * ((scores >= 9).sum() - (scores <= 6).sum()) / len(scores)


def nps_margin_of_error(scores: pd.Series, z: float = 1.96) -> float:
    """Approximate 95% margin of error of NPS (in points), multinomial variance."""
    n = len(scores)
    if n == 0:
        return float("nan")
    p = (scores >= 9).mean()
    d = (scores <= 6).mean()
    variance = p + d - (p - d) ** 2
    return float(100 * z * np.sqrt(variance / n))
