"""Case 1 page - Service operations & SLA."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..data.tickets import ROLLOUT
from ..engine import Engine
from ..viz import charts, theme
from .common import Tile, fmt, monitoring_table, pct, question, source_note, tiles

AGE_BUCKETS = [
    (0, 2, "0-2 days"),
    (2, 7, "3-7 days"),
    (7, 14, "8-14 days"),
    (14, 30, "15-30 days"),
    (30, 1e9, "> 30 days"),
]


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    df = t["tickets"]
    resolved = df[df["status"].eq("resolved")].copy()
    resolved["quarter"] = resolved["resolved_at"].dt.to_period("Q")
    last_q = resolved["quarter"].max()
    prev_q = last_q - 1
    rq, rp = resolved[resolved["quarter"].eq(last_q)], resolved[resolved["quarter"].eq(prev_q)]
    created_q = df[df["created_at"].dt.to_period("Q").eq(last_q)]

    v = {
        k: e.compute(k, rq)
        for k in ["sla_compliance", "resolution_time", "first_contact_resolution", "reopen_rate"]
    }
    vp = {k: e.compute(k, rp) for k in v}
    frt = e.compute("first_response_time", created_q)
    backlog = e.compute("backlog_aged_share", df)
    age_limit = e.catalog["backlog_aged_share"].params["age_limit_days"]
    target = e.catalog["sla_compliance"].target

    # ---- monthly SLA trend
    monthly = e.compute_by("sla_compliance", resolved, "resolved_month")
    below = monthly[monthly["value"] < target]
    first_below = below["resolved_month"].min() if len(below) else None
    # ---- by queue in the last quarter
    by_queue = e.compute_by("sla_compliance", rq, "queue").sort_values("value")
    worst = by_queue.iloc[0]
    others = by_queue.iloc[1:]
    # ---- backlog
    open_ = df[df["status"].eq("open")].copy()
    open_["bucket"] = pd.cut(
        open_["age_days"],
        bins=[b[0] for b in AGE_BUCKETS] + [AGE_BUCKETS[-1][1]],
        labels=[b[2] for b in AGE_BUCKETS],
    )
    worst_open = open_[open_["queue"].eq(worst["queue"])]
    aged_worst = e.compute("backlog_aged_share", worst_open)
    # ---- resolution tail for the worst queue
    wq = resolved[resolved["queue"].eq(worst["queue"])]
    tail = (
        wq.groupby("resolved_month")["resolution_hours"]
        .agg(median="median", p90=lambda s: s.quantile(0.9))
        .reset_index()
    )
    before = wq[wq["created_at"] < ROLLOUT]
    after = wq[wq["created_at"] >= ROLLOUT]
    med_b, med_a = before["resolution_hours"].median(), after["resolution_hours"].median()
    p90_b, p90_a = before["resolution_hours"].quantile(0.9), after["resolution_hours"].quantile(0.9)
    # ---- reopen rate
    reopen_b, reopen_a = e.compute("reopen_rate", before), e.compute("reopen_rate", after)
    other_q = resolved[~resolved["queue"].eq(worst["queue"])]
    reopen_others = e.compute("reopen_rate", other_q[other_q["created_at"] >= ROLLOUT])
    # ---- demand gap
    weeks_b = before["created_week"].nunique() or 1
    weeks_a = (
        df[(df["queue"].eq(worst["queue"])) & (df["created_at"] >= ROLLOUT)][
            "created_week"
        ].nunique()
        or 1
    )
    arrivals_b = len(df[(df["queue"].eq(worst["queue"])) & (df["created_at"] < ROLLOUT)]) / weeks_b
    arrivals_a = len(df[(df["queue"].eq(worst["queue"])) & (df["created_at"] >= ROLLOUT)]) / weeks_a

    md = ["# Case 1 · Service operations & SLA\n", source_note(manifest, ["tickets"])]
    md.append(
        "## Context\n\n"
        f"A service desk with four queues handled **{len(df):,} tickets** in 2024. Each priority carries a "
        "resolution promise (SLA): P1 8 h, P2 24 h, P3 72 h, P4 120 h. Agents pick the highest priority first, "
        f"then the oldest ticket. On **{ROLLOUT:%d %B %Y}** a product rollout started generating more field visits.\n\n"
    )
    md.append(
        "## Question\n\n"
        + question("Are we keeping the resolution promise - and if not, where, since when and why?")
    )
    md.append(f"## KPIs · {last_q}\n\n")
    md.append(
        tiles(
            e,
            [
                Tile(
                    "sla_compliance",
                    v["sla_compliance"],
                    f"{prev_q}: {fmt(e, 'sla_compliance', vp['sla_compliance'])}",
                ),
                Tile(
                    "resolution_time",
                    v["resolution_time"],
                    f"{prev_q}: {fmt(e, 'resolution_time', vp['resolution_time'])}",
                ),
                Tile("first_response_time", frt, f"tickets created in {last_q}"),
                Tile("backlog_aged_share", backlog, f"{len(open_)} open tickets at year end"),
                Tile(
                    "first_contact_resolution",
                    v["first_contact_resolution"],
                    f"{prev_q}: {fmt(e, 'first_contact_resolution', vp['first_contact_resolution'])}",
                ),
                Tile(
                    "reopen_rate",
                    v["reopen_rate"],
                    f"{prev_q}: {fmt(e, 'reopen_rate', vp['reopen_rate'])}",
                ),
            ],
        )
    )
    md.append(
        "SLA compliance is the outcome the customer feels; it is **lagging** (measured when a ticket closes). "
        "Aged backlog is its **leading** indicator: today's old tickets are next month's breaches. "
        "Reopen rate is the **counterweight** that stops speed being bought with quality.\n\n"
    )

    # ------------------------------------------------------------------ Finding
    md.append("## Finding\n\n")
    when = f"from {first_below:%B}" if first_below is not None else "at no point"
    fig = charts.line(
        monthly["resolved_month"], monthly["value"],
        conclusion=f"SLA compliance fell below the {pct(target)} target {when} and has not recovered",
        subtitle="Share of resolved tickets closed within their priority's SLA, by month of resolution (axis starts at 60%)",
        name="SLA compliance",
    )  # fmt: skip
    charts.add_target(fig, target, f"Target {pct(target)}")
    charts.annotate(
        fig,
        ROLLOUT,
        float(monthly.loc[monthly["resolved_month"].eq(ROLLOUT), "value"].iloc[0]),
        "Product rollout",
        ay=-50,
    )
    fig.update_yaxes(range=[0.6, 1.0])
    md.append(
        charts.to_html(
            fig,
            table=monthly.assign(value=monthly["value"].map(pct)).rename(
                columns={"resolved_month": "month"}
            ),
        )
    )

    fig = charts.bar(
        by_queue["queue"], by_queue["value"],
        conclusion=f"One queue explains the breach: {worst['queue']} at {pct(worst['value'])}, the others at "
        f"{pct(others['value'].min())}-{pct(others['value'].max())}",
        subtitle=f"SLA compliance by queue, tickets resolved in {last_q}",
        highlight={worst["queue"]}, text=[pct(x, 1) for x in by_queue["value"]],
    )  # fmt: skip
    charts.add_target(fig, target, f"Target {pct(target)}", axis="x")
    fig.update_xaxes(range=[0, 1.12])
    md.append(charts.to_html(fig, height=320))

    counts = open_.groupby(["queue", "bucket"], observed=False).size().unstack("bucket").fillna(0)
    counts = counts.loc[counts.sum(axis=1).sort_values(ascending=False).index]
    fig = go.Figure()
    for color, (_, _, label) in zip(theme.ORDINAL, AGE_BUCKETS, strict=True):
        fig.add_trace(go.Bar(y=counts.index, x=counts[label], name=label, orientation="h", marker_color=color,
                             hovertemplate=f"%{{y}} · {label}: %{{x}} tickets<extra></extra>"))  # fmt: skip
    fig.update_layout(
        barmode="stack",
        title=theme.title(
            f"{len(worst_open)} of {len(open_)} open tickets sit in {worst['queue']}; "
            f"{pct(aged_worst)} are older than {age_limit} days",
            "Open tickets at year end by queue and age - these are next month's SLA breaches",
        ),
    )
    fig.update_yaxes(autorange="reversed")
    md.append(charts.to_html(fig, height=340, table=counts.reset_index()))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tail["resolved_month"], y=tail["median"], name="Median", mode="lines+markers",
                             line=dict(color=theme.CONTEXT_DARK, width=2)))  # fmt: skip
    fig.add_trace(go.Scatter(x=tail["resolved_month"], y=tail["p90"], name="90th percentile", mode="lines+markers",
                             line=dict(color=theme.HIGHLIGHT, width=2.5)))  # fmt: skip
    for col, label, color in (
        ("median", "Median", theme.CONTEXT_DARK),
        ("p90", "P90", theme.HIGHLIGHT),
    ):
        fig.add_annotation(x=tail["resolved_month"].iloc[-1], y=tail[col].iloc[-1], text=label, showarrow=False,
                           xanchor="left", xshift=8, font=dict(color=color, size=12))  # fmt: skip
    fig.update_layout(
        showlegend=True,
        title=theme.title(
            f"The typical ticket slowed {med_a / med_b:.1f}x; the slowest 10% slowed {p90_a / p90_b:.1f}x",
            f"{worst['queue']}: resolution hours by month - median vs 90th percentile",
        ),
    )
    fig.update_yaxes(title_text="hours", ticksuffix=" h")
    md.append(charts.to_html(fig, height=360))

    reopen = e.compute_by("reopen_rate", resolved.assign(
        group=resolved["queue"].where(resolved["queue"].eq(worst["queue"]), "Other queues")), ["group", "resolved_month"])  # fmt: skip
    fq = reopen[reopen["group"].eq(worst["queue"])]
    oq = reopen[reopen["group"].eq("Other queues")]
    fig = charts.line(
        fq["resolved_month"], fq["value"],
        conclusion=f"Under pressure, reopenings rose from {pct(reopen_b, 1)} to {pct(reopen_a, 1)} in {worst['queue']}",
        subtitle="Reopen rate by month of resolution; other queues in grey for reference",
        name=worst["queue"], yformat=".0%", context={"Other queues": (oq["resolved_month"], oq["value"])},
    )  # fmt: skip
    charts.add_target(
        fig, e.catalog["reopen_rate"].target, f"Target {pct(e.catalog['reopen_rate'].target)}"
    )
    md.append(charts.to_html(fig, height=340))

    md.append(
        "**Reading it together.** Since the rollout, "
        f"{worst['queue']} receives about **{arrivals_a:.0f} tickets a week instead of {arrivals_b:.0f}** "
        f"(+{arrivals_a / arrivals_b - 1:.0%}) with the same team. Priority rules protect P1/P2, so the "
        f"wait piles up in P3/P4 and in the backlog. The fleet median resolution time "
        f"({fmt(e, 'resolution_time', v['resolution_time'])}) barely moves - the problem lives in the tail "
        f"and in one queue. Reopenings in the other queues stayed at {pct(reopen_others, 1)}: the quality "
        "drop is local too.\n\n"
    )

    # ----------------------------------------------------------------- Decision
    md.append(
        "## Decision\n\n"
        f"1. **Close the capacity gap in {worst['queue']}** - the gap is about "
        f"{arrivals_a - arrivals_b:.0f} tickets a week. Options: reassign trained agents from the queues that are "
        "well above target, or overtime for a burn-down period. Size it with the gap, not with the SLA percentage.\n"
        f"2. **Burn down the aged backlog first** - {int((worst_open['age_days'] > age_limit).sum())} tickets are "
        f"already older than {age_limit} days. A daily stand-up on the oldest tickets is cheaper than the "
        "breaches they will cause.\n"
        "3. **Do not reward closure speed alone** - pair every resolution-time target with the reopen rate, "
        "so agents are not pushed to close tickets that come back.\n\n"
    )
    md.append(
        "## How we keep measuring\n\n"
        + monitoring_table(
            e,
            [
                (
                    "backlog_aged_share",
                    "Weekly, per queue (leading)",
                    "> 20% in any queue for 2 weeks",
                ),
                ("sla_compliance", "Monthly, per queue and priority", "Below 85% in any queue"),
                ("resolution_time", "Weekly, median and P90", "P90 above the SLA of the priority"),
                ("reopen_rate", "Weekly, per queue", "Above 8% - review closed tickets"),
                ("first_contact_resolution", "Monthly, per channel", "Below 60% in a channel"),
            ],
        )
        + "The aged-backlog rule fires weeks before SLA compliance drops, which is why it is reviewed weekly.\n"
    )
    return "\n".join(md)
