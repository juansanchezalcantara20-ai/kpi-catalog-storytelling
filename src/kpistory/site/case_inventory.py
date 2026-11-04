"""Case 3 page - Inventory & demand."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..data.inventory import MA_WEEKS, N_FADED, N_TOP, ORDER_UP_TO_WEEKS
from ..engine import Engine
from ..viz import charts, theme
from .common import Tile, monitoring_table, pct, question, source_note, tiles


def _abc(forecast: pd.DataFrame) -> pd.Series:
    """A = SKUs making the first 80% of units, B = next 15%, C = rest."""
    units = forecast.groupby("sku")["actual_units"].sum().sort_values(ascending=False)
    share = units.cumsum() / units.sum()
    cls = pd.Series("C", index=units.index)
    cls[share <= 0.80] = "A"
    cls[(share > 0.80) & (share <= 0.95)] = "B"
    cls.iloc[0] = "A"
    return cls


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    ol, daily, snap, fc = (
        t["order_lines"],
        t["inventory_daily"],
        t["inventory_snapshot"],
        t["forecast"],
    )
    end = daily["date"].max()
    start12 = end - pd.Timedelta(days=364)
    ol12 = ol[ol["order_date"] >= start12]
    d12 = daily[daily["date"] >= start12]
    fc12 = fc[fc["week"] >= start12]
    period = f"{start12:%b %Y} - {end:%b %Y}"

    v = {
        "fill_rate": e.compute("fill_rate", ol12),
        "otif": e.compute("otif", ol12),
        "stockout_rate": e.compute("stockout_rate", d12),
        "inventory_turnover": e.compute("inventory_turnover", d12),
        "days_of_cover": e.compute("days_of_cover", d12[d12["sku"].isin(snap.loc[snap["sku_group"].eq("Best seller"), "sku"])]),
        "obsolescence_share": e.compute("obsolescence_share", snap),
        "wape": e.compute("wape", fc12),
        "mape": e.compute("mape", fc12),
        "forecast_bias": e.compute("forecast_bias", fc12),
    }  # fmt: skip

    md = ["# Case 3 · Inventory & demand\n", source_note(manifest, ["transactions", "inventory"])]
    md.append(
        "## Context\n\n"
        f"An online gift retailer sells mostly to small shops; demand peaks before Christmas. The planning "
        f"team forecasts each SKU with an **{MA_WEEKS}-week moving average**, reviews stock every Monday and "
        f"orders up to {ORDER_UP_TO_WEEKS:.0f} weeks of forecast from suppliers with a 10-17 day lead time. "
        f"The case follows the {N_TOP} best-selling SKUs plus {N_FADED} SKUs whose demand faded.\n\n"
    )
    md.append("## Question\n\n" + question(
        "Is our stock serving customers without tying up capital - and what breaks the balance?"
    ))  # fmt: skip
    md.append(f"## KPIs · {period}\n\n")
    md.append(tiles(e, [
        Tile("fill_rate", v["fill_rate"], "units shipped / ordered"),
        Tile("otif", v["otif"], "complete and on time, per order"),
        Tile("stockout_rate", v["stockout_rate"], "active SKU-days at zero"),
        Tile("days_of_cover", v["days_of_cover"], f"best sellers, {end:%d %b %Y}"),
        Tile("inventory_turnover", v["inventory_turnover"], "annualised, at cost"),
        Tile("obsolescence_share", v["obsolescence_share"], f"stock value, {end:%d %b %Y}"),
        Tile("wape", v["wape"], "weekly, SKU level"),
        Tile("mape", v["mape"], "same forecasts as WAPE"),
        Tile("forecast_bias", v["forecast_bias"], "+ = over-forecast"),
    ]))  # fmt: skip
    md.append(
        "Service (fill rate, OTIF, stockouts) and capital (cover, turnover, obsolescence) pull in opposite "
        "directions; forecast accuracy and **bias** sit upstream of both.\n\n"
    )

    md.append("## Finding\n\n")
    # 1 - OTIF decomposition
    lines = ol12.assign(
        short=ol12["qty_shipped"] < ol12["qty_ordered"],
        late=ol12["delivered_date"] > ol12["promised_date"],
    )
    orders = lines.groupby("order_id")[["short", "late"]].any()
    cats = pd.Series(
        {
            "On time, in full": (~orders["short"] & ~orders["late"]).mean(),
            "Short only": (orders["short"] & ~orders["late"]).mean(),
            "Late only": (~orders["short"] & orders["late"]).mean(),
            "Short and late": (orders["short"] & orders["late"]).mean(),
        }
    )
    failures = cats.drop("On time, in full").sort_values(ascending=False)
    top_fail = failures.index[0]
    order_size = lines.groupby("order_id").size().mean()
    fig = charts.bar(
        list(cats.index), cats.values,
        conclusion=f"Fill rate is {pct(v['fill_rate'])}, yet only {pct(v['otif'])} of orders arrive complete "
        f"and on time - most failures are '{top_fail.lower()}'",
        subtitle=f"Share of orders by outcome, {period} (an order has {order_size:.1f} lines of these SKUs on average)",
        highlight={top_fail}, text=[pct(x, 1) for x in cats.values],
        colors=[theme.STATUS["green"] if c == "On time, in full" else (theme.HIGHLIGHT if c == top_fail else theme.CONTEXT) for c in cats.index],
    )  # fmt: skip
    fig.update_xaxes(range=[0, 1.1])
    md.append(
        charts.to_html(
            fig,
            height=320,
            table=cats.rename("share of orders")
            .map(pct)
            .reset_index()
            .rename(columns={"index": "outcome"}),
        )
    )
    md.append(
        f"Fill rate counts **units**; OTIF counts **orders**. With {order_size:.1f} lines per order, one short "
        "line fails the whole order - that is why the two KPIs can tell such different stories.\n\n"
    )

    # 2 - bias by month
    mb = e.compute_by(
        "forecast_bias", fc.assign(month=fc["week"].dt.to_period("M").dt.start_time), "month"
    )
    mb = mb[
        (mb["month"] >= start12 - pd.Timedelta(days=62))
        & (mb["month"] + pd.offsets.MonthEnd(0) <= end)
    ]
    lo_band, hi_band = e.catalog["forecast_bias"].thresholds["green"]
    lowest, highest = mb.loc[mb["value"].idxmin()], mb.loc[mb["value"].idxmax()]
    colors = [
        theme.SECOND if x < lo_band else theme.HIGHLIGHT if x > hi_band else theme.CONTEXT
        for x in mb["value"]
    ]
    fig = go.Figure(go.Bar(x=mb["month"], y=mb["value"], marker_color=colors,
                           hovertemplate="%{x|%b %Y}: %{y:+.1%}<extra></extra>"))  # fmt: skip
    charts.add_band(fig, lo_band, hi_band)
    fig.add_hline(y=0, line=dict(color=theme.INK_2, width=1))
    charts.annotate(
        fig,
        lowest["month"],
        lowest["value"],
        f"under-forecast {lowest['value']:+.0%}<br>→ stockouts",
        ay=40,
    )
    charts.annotate(
        fig,
        highest["month"],
        highest["value"],
        f"over-forecast {highest['value']:+.0%}<br>→ excess stock",
        ay=-40,
    )
    fig.update_layout(title=theme.title(
        f"The moving average lags the season: {lowest['value']:+.0%} in {lowest['month']:%b %Y}, "
        f"{highest['value']:+.0%} in {highest['month']:%b %Y}",
        f"Forecast bias by month ((forecast - actual) / actual); green band = ±{hi_band:.0%}; "
        "orange = under-forecast, blue = over-forecast"))  # fmt: skip
    fig.update_yaxes(tickformat="+.0%", rangemode="normal")
    md.append(charts.to_html(fig, height=380))

    # 3 - stockouts by week
    sw = e.compute_by(
        "stockout_rate", d12.assign(week=d12["date"].dt.to_period("W-SUN").dt.start_time), "week"
    )
    so = d12[d12["active"] & (d12["on_hand_units"] <= 0)]
    under_months = set(mb.loc[mb["value"] < lo_band, "month"])
    under_share = (
        so["date"].dt.to_period("M").dt.start_time.isin(under_months).mean()
        if len(so)
        else float("nan")
    )
    peak = sw.loc[sw["value"].idxmax()]
    fig = charts.line(
        sw["week"], sw["value"],
        conclusion=f"Stockouts peak at {pct(peak['value'])} in the week of {peak['week']:%d %b %Y}; "
        + (
            f"{pct(under_share)} of stockout days fall in under-forecast months"
            if under_share >= 0.5
            else f"only {pct(under_share)} fall in under-forecast months - the rest is demand variability "
            "that no safety stock covers"
        ),
        subtitle="Weekly stockout rate (share of active SKU-days with zero stock)",
        name="Stockout rate", yformat=".0%",
    )  # fmt: skip
    charts.add_target(
        fig, e.catalog["stockout_rate"].target, f"Target {pct(e.catalog['stockout_rate'].target)}"
    )
    for m in sorted(under_months):
        fig.add_vrect(
            x0=m,
            x1=m + pd.offsets.MonthEnd(1),
            fillcolor="rgba(235,104,52,0.08)",
            line_width=0,
            layer="below",
        )
    if under_months:
        fig.add_annotation(x=max(under_months), y=1, yref="paper", text="shaded: under-forecast months", showarrow=False,
                           xanchor="right", font=dict(color=theme.INK_2, size=11))  # fmt: skip
    md.append(charts.to_html(fig, height=340))

    # 4 - why MAPE and WAPE disagree: APE by size of the weekly actual
    f = fc12[fc12["actual_units"] > 0].copy()
    f["ape"] = (f["actual_units"] - f["forecast_units"]).abs() / f["actual_units"]
    edges = [0, 9, 49, 199, float("inf")]
    labels = ["1-9 units", "10-49 units", "50-199 units", "200+ units"]
    f["size"] = pd.cut(f["actual_units"], edges, labels=labels)
    acc = f.groupby("size", observed=False).agg(
        rows=("ape", "size"), mape=("ape", "mean"), units=("actual_units", "sum")
    )
    acc["row_share"] = acc["rows"] / acc["rows"].sum()
    acc["unit_share"] = acc["units"] / acc["units"].sum()
    small_rows = f["actual_units"] < 50
    contrib = f.loc[small_rows, "ape"].sum() / f["ape"].sum()
    fig = charts.bar(
        labels, acc["mape"].values,
        conclusion=f"MAPE says {pct(v['mape'])}, WAPE says {pct(v['wape'])}: the {pct(small_rows.mean())} of "
        f"SKU-weeks selling under 50 units produce {pct(contrib)} of MAPE",
        subtitle="Average absolute % error (MAPE) of SKU-weeks, by size of the actual weekly demand",
        highlight={labels[0]}, horizontal=False,
        text=[pct(m) for m in acc["mape"]],
    )  # fmt: skip
    md.append(charts.to_html(fig, height=380, table=acc.reset_index().round(3)))
    md.append(
        "MAPE gives every SKU-week the same vote, so small weeks - where missing by 5 units is a 100% error - "
        "dominate it. WAPE weights errors by units, which is what stock and service feel.\n\n"
    )

    # 5 - obsolescence
    age_limit = e.catalog["obsolescence_share"].params["age_limit_days"]
    snap2 = snap.assign(bucket=pd.cut(snap["days_since_last_movement"], [-1, 30, 90, age_limit, 10**6],
                                      labels=["≤ 30 days", "31-90 days", f"91-{age_limit} days", f"> {age_limit} days"]))  # fmt: skip
    val = snap2.groupby("bucket", observed=False)["on_hand_value"].sum()
    old = snap2[snap2["days_since_last_movement"] > age_limit]
    faded_old = old["sku_group"].eq("Faded").sum()
    fig = charts.bar(
        [str(b) for b in val.index], val.values,
        conclusion=f"{pct(v['obsolescence_share'])} of stock value has not moved for {age_limit}+ days - "
        f"{faded_old} of those {len(old)} SKUs are faded items",
        subtitle=f"Stock value at cost by days since the last sale, {end:%d %b %Y}",
        highlight={f"> {age_limit} days"}, xformat=",.0f", horizontal=False, text=[f"{x:,.0f}" for x in val.values],
    )  # fmt: skip
    md.append(charts.to_html(fig, height=340))

    # 6 - days of cover distribution
    last = daily[daily["date"] >= end - pd.Timedelta(days=55)]
    best = snap.loc[snap["sku_group"].eq("Best seller"), "sku"]
    cover = pd.Series(
        {s: e.compute("days_of_cover", last[last["sku"].eq(s)]) for s in best}
    ).replace(float("inf"), 999)
    g_lo, g_hi = e.catalog["days_of_cover"].thresholds["green"]
    low_n, high_n = int((cover < g_lo).sum()), int((cover > g_hi).sum())
    fig = go.Figure(go.Histogram(x=cover.clip(upper=120), xbins=dict(start=0, size=5), marker_color=theme.CONTEXT_DARK,
                                 hovertemplate="%{x} days: %{y} SKUs<extra></extra>"))  # fmt: skip
    charts.add_band(fig, g_lo, g_hi, axis="x")
    fig.add_annotation(
        x=(g_lo + g_hi) / 2,
        y=1,
        yref="paper",
        text="target band",
        showarrow=False,
        font=dict(color=theme.INK_2),
    )
    fig.update_layout(title=theme.title(
        f"Only {len(cover) - low_n - high_n} of {len(cover)} best sellers sit in the {g_lo:.0f}-{g_hi:.0f} day band: "
        f"{low_n} too low, {high_n} too high",
        f"Days of cover per SKU at {end:%d %b %Y} (demand of the last 8 weeks; values above 120 shown at 120)"))  # fmt: skip
    fig.update_xaxes(title_text="days of cover")
    fig.update_yaxes(title_text="SKUs")
    md.append(charts.to_html(fig, height=340))
    md.append(
        "A single fleet-level days-of-cover number nets these two tails against each other - that is why the "
        "catalog defines it with a band and why the distribution is the recommended chart.\n\n"
    )

    md.append(
        "## Decision\n\n"
        "1. **Forecast the season, not the last 8 weeks.** For seasonal SKUs use last year's same weeks × trend "
        "(or a seasonal model) from September; keep the moving average only for flat SKUs. Track **bias** "
        "monthly - it is the error you can fix.\n"
        "2. **Pre-build stock before the peak** for A-class seasonal SKUs, sized with the seasonal forecast "
        "and the 10-17 day lead time, instead of reacting to stockouts in November.\n"
        f"3. **Clear the {len(old)} SKUs without sales for {age_limit}+ days** (markdown, bundle or return) and "
        "add a stop-ordering rule when a SKU's demand drops for 8 weeks.\n"
        + (
            "4. **Size safety stock per SKU** from demand variability and lead time instead of a flat 5 weeks: "
            "most stockouts happen outside under-forecast months.\n"
            if under_share < 0.5
            else ""
        )
        + "4. **Split OTIF failures by owner** - short lines belong to planning (stock), late deliveries to "
        f"logistics and the carrier. Today the largest group is '{top_fail.lower()}', so the first "
        f"conversation is with {'logistics' if 'Late' in top_fail else 'planning'}.\n"
        "5. **Report WAPE and bias as the headline accuracy KPIs**, MAPE only for the long tail.\n\n"
    )
    md.append(
        "## How we keep measuring\n\n"
        + monitoring_table(
            e,
            [
                ("forecast_bias", "Monthly, per SKU class (leading)", "Outside ±10% for a class"),
                ("days_of_cover", "Weekly, per SKU", "Below 7 days on an A SKU - expedite"),
                ("otif", "Weekly, split into short / late", "Below 80% for 2 weeks"),
                ("stockout_rate", "Weekly", "Above 6% in season"),
                ("obsolescence_share", "Monthly", "Above 10% of stock value"),
                ("wape", "Monthly", "Above 45%"),
            ],
        )  # fmt: skip
    )
    return "\n".join(md)
