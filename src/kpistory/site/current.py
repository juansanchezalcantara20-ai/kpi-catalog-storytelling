"""Headline value of every KPI on its case data (used by the catalog pages and Power BI notes)."""

from __future__ import annotations

import pandas as pd

from ..engine import Engine

# KPI -> processed table it is computed on, for the "current value" shown in the catalog.
TABLE_OF = {
    "first_response_time": "tickets", "resolution_time": "tickets", "sla_compliance": "tickets",
    "backlog_aged_share": "tickets", "first_contact_resolution": "tickets", "reopen_rate": "tickets",
    "mtbf": "asset_periods", "mttr": "work_orders", "availability": "asset_periods",
    "pm_compliance": "work_orders", "planned_work_share": "work_orders",
    "fill_rate": "order_lines", "otif": "order_lines", "inventory_turnover": "inventory_daily",
    "days_of_cover": "inventory_daily", "stockout_rate": "inventory_daily",
    "obsolescence_share": "inventory_snapshot", "mape": "forecast", "wape": "forecast",
    "forecast_bias": "forecast", "retention_rate": "customer_sales", "repeat_purchase_rate": "customer_sales",
    "revenue_at_risk_share": "customer_rfm", "nps": "survey",
}  # fmt: skip


def current_values(tables: dict[str, pd.DataFrame], engine: Engine) -> dict[str, float]:
    out = {k: engine.compute(k, tables[t]) for k, t in TABLE_OF.items() if t in tables}
    dq = tables.get("dq_results")
    if dq is not None:
        for dim in ["completeness", "uniqueness", "validity", "timeliness"]:
            d = dq[dq["dimension"].eq(dim) & (dq["total"] > 0)]
            out[f"dq_{dim}"] = d["passed"].sum() / d["total"].sum()
    return out
