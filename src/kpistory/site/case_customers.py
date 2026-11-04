"""Case 4 page - Customers."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..engine import Engine
from ..formulas.customers import PANDAS_PERIOD, nps_margin_of_error, retention_series
from ..viz import charts, theme
from .common import Tile, monitoring_table, pct, question, source_note, tiles

SEGMENT_ORDER = [
    "Champions",
    "Loyal",
    "New / promising",
    "Needs attention",
    "At risk",
    "Hibernating",
]


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    sales, cs, rfm, survey = t["sales"], t["customer_sales"], t["customer_rfm"], t["survey"]
    end = sales["invoice_date"].max()
    period = e.catalog["retention_rate"].params["period"]
    ret = retention_series(cs, period)
    # Drop the last period if it is incomplete (the log ends mid-quarter).
    last_p = cs["invoice_date"].max().to_period(PANDAS_PERIOD[period])
    if cs["invoice_date"].max() < last_p.end_time.normalize():
        ret = ret.drop(index=str(last_p), errors="ignore")
    window = cs[cs["invoice_date"] > end - pd.Timedelta(days=365)]
    anon_rev = 1 - cs["revenue"].sum() / sales["revenue"].sum()

    nps = e.compute("nps", survey)
    moe = nps_margin_of_error(survey["score"])
    v = {
        "retention_rate": float(ret.iloc[-1]),
        "repeat_purchase_rate": e.compute("repeat_purchase_rate", window),
        "revenue_at_risk_share": e.compute("revenue_at_risk_share", rfm),
        "nps": nps,
    }

    md = ["# Case 4 · Customers\n", source_note(manifest, ["transactions", "survey"])]
    md.append(
        "## Context\n\n"
        f"The same retailer as case 3. **{cs['customer_id'].nunique():,} identified customers** placed orders "
        f"between {sales['invoice_date'].min():%b %Y} and {end:%b %Y}; guest checkouts have no customer id and "
        f"represent {pct(anon_rev)} of revenue (they are excluded here and measured in case 5). "
        f"An NPS survey reached the customers active in the last 12 months ({len(survey):,} responses, simulated).\n\n"
    )
    md.append(
        "## Question\n\n"
        + question("Are we keeping our customers - and whom should we call first?")
    )
    md.append(f"## KPIs · last 12 months to {end:%d %b %Y}\n\n")
    md.append(tiles(e, [
        Tile("retention_rate", v["retention_rate"], f"{ret.index[-1]} vs previous quarter"),
        Tile("repeat_purchase_rate", v["repeat_purchase_rate"], "2+ invoices in 12 months"),
        Tile("revenue_at_risk_share", v["revenue_at_risk_share"], f"{int((rfm['segment'] == 'At risk').sum())} customers"),
        Tile("nps", v["nps"], f"n = {len(survey)}, ±{moe:.0f} points (95%)"),
    ]))  # fmt: skip
    md.append(
        "Retention is the outcome; **revenue at risk** is the leading indicator and, more usefully, a list of "
        "names. NPS adds the customer's voice - read with its sample size.\n\n"
    )

    md.append("## Finding\n\n")
    rs = ret.reset_index()
    rs.columns = ["quarter", "value"]
    lo, hi = rs.loc[rs["value"].idxmin()], rs.loc[rs["value"].idxmax()]
    fig = charts.line(
        rs["quarter"], rs["value"],
        conclusion=f"Quarterly retention moves between {pct(lo['value'])} ({lo['quarter']}) and {pct(hi['value'])} "
        f"({hi['quarter']}) - {pct(1 - rs['value'].mean())} of a quarter's buyers do not come back the next one",
        subtitle="Share of the previous quarter's customers who bought again in the quarter (complete quarters only)",
        name="Retention",
    )  # fmt: skip
    charts.add_target(
        fig, e.catalog["retention_rate"].target, f"Target {pct(e.catalog['retention_rate'].target)}"
    )
    fig.update_yaxes(range=[0, 1])
    md.append(charts.to_html(fig, height=340, table=rs.assign(value=rs["value"].map(pct))))

    seg = rfm.groupby("segment").agg(
        customers=("customer_id", "count"), revenue=("monetary", "sum")
    )
    seg = seg.reindex([s for s in SEGMENT_ORDER if s in seg.index])
    seg["share"] = seg["revenue"] / seg["revenue"].sum()
    seg = seg.sort_values("revenue", ascending=False)
    risk = rfm[rfm["segment"].eq("At risk")].sort_values("monetary", ascending=False)
    half = (
        int((risk["monetary"].cumsum() <= risk["monetary"].sum() / 2).sum()) + 1 if len(risk) else 0
    )
    fig = charts.bar(
        seg.index, seg["share"],
        conclusion=f"'At risk' customers - good buyers gone quiet - hold {pct(v['revenue_at_risk_share'])} of revenue; "
        f"{half} of them make half of it",
        subtitle="Share of last-12-month revenue by RFM segment",
        highlight={"At risk"}, text=[f"{pct(s)} · {c} customers" for s, c in zip(seg["share"], seg["customers"], strict=True)],
    )  # fmt: skip
    fig.update_xaxes(range=[0, seg["share"].max() * 1.35])
    md.append(
        charts.to_html(
            fig, height=340, table=seg.reset_index().assign(share=seg["share"].map(pct).values)
        )
    )

    rows = []
    for s in SEGMENT_ORDER:
        sub = survey[survey["segment"].eq(s)]
        if len(sub) >= 10:
            rows.append(
                {
                    "segment": s,
                    "n": len(sub),
                    "nps": e.compute("nps", sub),
                    "moe": nps_margin_of_error(sub["score"]),
                }
            )
    by_seg = pd.DataFrame(rows).sort_values("nps")
    fig = go.Figure(go.Scatter(
        x=by_seg["nps"], y=by_seg["segment"], mode="markers",
        error_x=dict(type="data", array=by_seg["moe"], color=theme.CONTEXT_DARK, thickness=1.5, width=6),
        marker=dict(size=11, color=[theme.HIGHLIGHT if s == "At risk" else theme.CONTEXT_DARK for s in by_seg["segment"]]),
        customdata=by_seg[["n", "moe"]], hovertemplate="%{y}: NPS %{x:+.0f} ± %{customdata[1]:.0f} (n = %{customdata[0]})<extra></extra>"))  # fmt: skip
    fig.add_vline(x=0, line=dict(color=theme.INK_2, width=1))
    best, worst = by_seg.iloc[-1], by_seg.iloc[0]
    fig.update_layout(title=theme.title(
        f"NPS goes from {best['nps']:+.0f} ({best['segment']}) to {worst['nps']:+.0f} ({worst['segment']}); "
        "the error bars show which gaps are real",
        "NPS by RFM segment with 95% margin of error (segments with at least 10 responses)"))  # fmt: skip
    fig.update_xaxes(
        range=[-100, 100], title_text="NPS", showgrid=True, gridcolor=theme.GRID, zeroline=False
    )
    md.append(charts.to_html(fig, height=360, table=by_seg.round(1)))

    det, pas, pro = (
        (survey["score"] <= 6).mean(),
        survey["score"].between(7, 8).mean(),
        (survey["score"] >= 9).mean(),
    )
    fig = go.Figure()
    for share, label, color in ((det, "Detractors (0-6)", theme.SECOND), (pas, "Passives (7-8)", theme.CONTEXT),
                                (pro, "Promoters (9-10)", theme.HIGHLIGHT)):  # fmt: skip
        fig.add_trace(go.Bar(y=["All respondents"], x=[share], name=label, orientation="h", marker_color=color,
                             text=[f"{label.split(' ')[0]} {pct(share)}"], textposition="inside", insidetextanchor="middle",
                             hovertemplate=f"{label}: {pct(share, 1)}<extra></extra>"))  # fmt: skip
    fig.update_layout(barmode="stack", showlegend=True, title=theme.title(
        f"NPS {nps:+.0f} = {pct(pro)} promoters - {pct(det)} detractors; the average score "
        f"({survey['score'].mean():.1f}/10) would hide that split",
        "Respondents by group - the only part-to-whole chart on the site, with exactly three parts"))  # fmt: skip
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    md.append(charts.to_html(fig, height=230))

    md.append(
        "*The NPS survey is simulated and its scores were drawn per RFM segment, so the link between segment "
        "and NPS is an assumption of the generator, not a finding. The chart shows how to read NPS: by "
        "segment, with n and a margin of error.*\n\n"
    )
    md.append(
        "## Decision\n\n"
        f"1. **Win-back campaign on the 'At risk' list, ordered by revenue.** The first {half} customers cover "
        "half of the revenue at risk - a call list for account managers, not a mass e-mail.\n"
        "2. **Close the loop with detractors** within 48 hours of their answer; their verbatims feed the "
        "service and inventory cases (late or short orders are the usual reasons).\n"
        "3. **Measure retention by acquisition cohort** before setting a single target: new cohorts behave "
        "differently from long-standing wholesale customers.\n"
        f"4. **Reduce guest checkouts** ({pct(anon_rev)} of revenue has no customer id) - every anonymous "
        "order is invisible to retention and RFM (see case 5).\n\n"
    )
    md.append(
        "## How we keep measuring\n\n"
        + monitoring_table(
            e,
            [
                (
                    "revenue_at_risk_share",
                    "Monthly, with the customer list (leading)",
                    "Above 20% - extend the campaign",
                ),
                ("retention_rate", "Quarterly, per acquisition cohort", "Below 40%"),
                ("repeat_purchase_rate", "Monthly, rolling 12 months", "Below 50%"),
                (
                    "nps",
                    "Per survey wave, with n and margin of error",
                    "A drop larger than the margin of error",
                ),
            ],
        )  # fmt: skip
    )
    return "\n".join(md)
