"""Reference value of every KPI: one number, one period, used everywhere.

The case tiles, the catalog pages and the dashboard all read from `headline()`, so the
same KPI can never show two different numbers on the site (tested in test_coherencia.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from ..engine import Engine
from ..formulas.customers import PANDAS_PERIOD, retention_series

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def mes(ts: pd.Timestamp) -> str:
    """Timestamp -> 'sep 2024'."""
    ts = pd.Timestamp(ts)
    return f"{MESES[ts.month - 1]} {ts.year}"


def fecha(ts: pd.Timestamp) -> str:
    """Timestamp -> '31 dic 2024'."""
    ts = pd.Timestamp(ts)
    return f"{ts.day} {MESES[ts.month - 1]} {ts.year}"


def trimestre(p: pd.Period | str) -> str:
    """Quarter -> 'oct–dic 2024' (never '2024Q4')."""
    p = pd.Period(p, freq="Q")
    first = (p.quarter - 1) * 3
    return f"{MESES[first]}–{MESES[first + 2]} {p.year}"


@dataclass
class Headline:
    value: float
    period: str  # human period label, e.g. "oct–dic 2024"
    note: str = ""  # e.g. why there is no value


def _last_full_quarter(dates: pd.Series) -> pd.Period:
    last = pd.Timestamp(dates.max())
    q = last.to_period("Q")
    return q if last >= q.end_time.normalize() else q - 1


def headline(
    t: dict[str, pd.DataFrame], e: Engine, manifest: dict | None = None
) -> dict[str, Headline]:
    manifest = manifest or {}
    out: dict[str, Headline] = {}
    unavailable = set((manifest.get("tickets") or {}).get("unavailable_kpis", []))

    # --- service: last complete quarter of resolution; backlog = snapshot at the cut-off
    tk = t["tickets"]
    res = tk[tk["status"].eq("resolved")]
    q = _last_full_quarter(res["resolved_at"])
    in_q = res[res["resolved_at"].dt.to_period("Q").eq(q)]
    for k in ("resolution_time", "sla_compliance", "first_contact_resolution", "reopen_rate"):
        out[k] = Headline(e.compute(k, in_q) if k not in unavailable else math.nan, trimestre(q))
    created_q = tk[tk["created_at"].dt.to_period("Q").eq(q)]
    out["first_response_time"] = Headline(
        e.compute("first_response_time", created_q)
        if "first_response_time" not in unavailable
        else math.nan,
        trimestre(q),
    )
    for k in unavailable:
        out[k].note = "La fuente pública no registra este dato."
    snap = manifest.get("tickets", {}).get("snapshot")
    out["backlog_aged_share"] = Headline(
        e.compute("backlog_aged_share", tk), f"abiertas al {fecha(snap)}" if snap else "al cierre"
    )

    # --- maintenance: the whole year of the process data
    ap, wo = t["asset_periods"], t["work_orders"]
    year = f"{mes(ap['month'].min())} – {mes(ap['month'].max())}"
    for k, df in (
        ("mtbf", ap),
        ("availability", ap),
        ("mttr", wo),
        ("pm_compliance", wo),
        ("planned_work_share", wo),
    ):
        out[k] = Headline(e.compute(k, df), year)

    # --- inventory: last 12 months; snapshots at the last date
    daily, ol, fc, snap_inv = (
        t["inventory_daily"],
        t["order_lines"],
        t["forecast"],
        t["inventory_snapshot"],
    )
    end = daily["date"].max()
    start12 = end - pd.Timedelta(days=364)
    p12 = f"{mes(start12)} – {mes(end)}"
    out["fill_rate"] = Headline(e.compute("fill_rate", ol[ol["order_date"] >= start12]), p12)
    out["otif"] = Headline(e.compute("otif", ol[ol["order_date"] >= start12]), p12)
    d12 = daily[daily["date"] >= start12]
    out["stockout_rate"] = Headline(e.compute("stockout_rate", d12), p12)
    out["inventory_turnover"] = Headline(e.compute("inventory_turnover", d12), p12)
    best = snap_inv.loc[snap_inv["sku_group"].eq("Más vendido"), "sku"]
    out["days_of_cover"] = Headline(
        e.compute("days_of_cover", d12[d12["sku"].isin(best)]), f"al {fecha(end)}"
    )
    out["obsolescence_share"] = Headline(
        e.compute("obsolescence_share", snap_inv), f"al {fecha(end)}"
    )
    f12 = fc[fc["week"] >= start12]
    for k in ("mape", "wape", "forecast_bias"):
        out[k] = Headline(e.compute(k, f12), p12)

    # --- customers
    cs, rfm, sv = t["customer_sales"], t["customer_rfm"], t["survey"]
    period = e.catalog["retention_rate"].params["period"]
    ret = retention_series(cs, period)
    last_p = cs["invoice_date"].max().to_period(PANDAS_PERIOD[period])
    if cs["invoice_date"].max() < last_p.end_time.normalize():
        ret = ret.drop(index=str(last_p), errors="ignore")
    out["retention_rate"] = Headline(
        float(ret.iloc[-1]), f"{trimestre(ret.index[-1])} frente al trimestre anterior"
    )
    cend = cs["invoice_date"].max()
    window = cs[cs["invoice_date"] > cend - pd.Timedelta(days=365)]
    out["repeat_purchase_rate"] = Headline(
        e.compute("repeat_purchase_rate", window), "últimos 12 meses"
    )
    out["revenue_at_risk_share"] = Headline(
        e.compute("revenue_at_risk_share", rfm), "últimos 12 meses"
    )
    out["nps"] = Headline(e.compute("nps", sv), f"{len(sv)} respuestas")

    # --- data quality: pooled over measurable datasets
    dq = t["dq_results"]
    for dim in ("completeness", "uniqueness", "validity", "timeliness"):
        d = dq[dq["dimension"].eq(dim) & (dq["total"] > 0)]
        out[f"dq_{dim}"] = Headline(
            d["passed"].sum() / d["total"].sum(), f"{len(d)} conjuntos de datos medidos"
        )
    return out


def current_values(
    t: dict[str, pd.DataFrame], e: Engine, manifest: dict | None = None
) -> dict[str, float]:
    return {k: h.value for k, h in headline(t, e, manifest).items()}
