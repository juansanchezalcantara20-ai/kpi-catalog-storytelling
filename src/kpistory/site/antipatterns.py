"""Anti-pattern gallery: the same data shown wrong and right, side by side."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..engine import Engine
from ..viz import charts, theme
from .common import pct

W = 34  # title wrap width for half-width charts
RAINBOW = [
    "#e6194b",
    "#3cb44b",
    "#ffe119",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#46f0f0",
    "#f032e6",
    "#bcf60c",
    "#fabebe",
]


def _pair(bad: go.Figure, good: go.Figure, height: int = 380) -> str:
    for fig in (bad, good):
        fig.update_layout(
            legend=dict(orientation="h", y=-0.18, yanchor="top", x=0, font=dict(size=10))
        )
    return (
        '<div class="pair">\n'
        f'<div class="bad"><p class="verdict">✕ Misleading</p>\n{charts.to_html(bad, height=height)}</div>\n'
        f'<div class="good"><p class="verdict">✓ Honest</p>\n{charts.to_html(good, height=height)}</div>\n'
        "</div>\n\n"
    )


def _plain_title(text: str) -> dict:
    """The 'bad' charts get descriptive titles - itself one of the anti-patterns."""
    return dict(text=f"<b>{text}</b>")


def build(t: dict[str, pd.DataFrame], e: Engine) -> str:
    md = [
        "# Anti-pattern gallery\n",
        "The same data, shown wrong (left) and right (right). Every pair uses the data of the cases, so the "
        "honest version is also the one used on the case pages. The misleading versions are not strawmen - "
        "each one is a default setting or a habit seen in real reporting.\n",
    ]

    # 1 ------------------------------------------------------------- truncated axis
    tk = t["tickets"]
    rq = tk[
        (tk["status"] == "resolved")
        & (tk["resolved_at"] >= tk["resolved_at"].max() - pd.Timedelta(days=91))
    ]
    q = e.compute_by("sla_compliance", rq, "queue").sort_values("value")
    good_q = q.iloc[1:]  # the three queues around target: the comparison where truncation bites
    lo = float(good_q["value"].min())
    bad = go.Figure(
        go.Bar(
            x=good_q["queue"],
            y=good_q["value"],
            marker_color=[theme.SECOND, theme.HIGHLIGHT, theme.THIRD],
        )
    )
    bad.update_layout(title=_plain_title("SLA compliance by queue"), showlegend=False)
    bad.update_yaxes(range=[lo - 0.01, 1.0], tickformat=".0%")
    good = charts.bar(
        good_q["queue"], good_q["value"], horizontal=False,
        conclusion="",
        subtitle="SLA compliance, last quarter; bars start at zero", text=[pct(x, 1) for x in good_q["value"]],
    )  # fmt: skip
    good.update_traces(
        textposition="inside", insidetextanchor="end", textfont=dict(color="#0b0b0b")
    )
    good.update_layout(title=theme.title(
        f"All three are within {(good_q['value'].max() - lo) * 100:.0f} points of each other", "SLA compliance, last quarter - bars start at zero", W))  # fmt: skip
    charts.add_target(good, e.catalog["sla_compliance"].target, "Target 90%")
    good.update_yaxes(range=[0, 1.08])
    md.append("## 1 · The axis that does not start at zero\n")
    md.append(_pair(bad, good))
    md.append(
        f"**Why the left one misleads.** Bar *length* encodes the value. Starting the axis at {pct(lo - 0.01)} "
        "turns a difference of a few points into bars that look several times longer, and the rainbow colours "
        "suggest the queues are different kinds of thing. **What the right one does:** zero baseline, one "
        "colour, the target as a reference line, and a title that says what the reader should conclude. "
        "(Lines and dots may zoom, because they encode position, not length - and should say so.)\n"
    )

    # 2 --------------------------------------------------------------- mean vs median
    wo = t["work_orders"]
    corr = wo[wo["wo_type"].eq("corrective")]
    modes = (
        corr.groupby("failure_label")["repair_hours"]
        .agg(["mean", "median", "count"])
        .sort_values("mean", ascending=False)
    )
    modes = modes[modes["count"] >= 10]
    bad = go.Figure(go.Bar(x=modes.index, y=modes["mean"], marker_color=theme.HIGHLIGHT))
    bad.update_layout(title=_plain_title("Average repair time by failure mode (h)"))
    good = go.Figure()
    for m in modes.index:
        good.add_trace(go.Box(y=corr.loc[corr["failure_label"].eq(m), "repair_hours"], name=m, marker_color=theme.CONTEXT_DARK,
                              line=dict(width=1.5), boxpoints="outliers", showlegend=False))  # fmt: skip
    worst = modes["mean"].idxmax()
    good.update_layout(title=theme.title(
        f"Typical repairs take {modes['median'].min():.1f}-{modes['median'].max():.1f} h; the means are pulled up by a few waits for parts",
        "Repair hours per corrective work order (box = middle 50%, line = median, dots = outliers)", W))  # fmt: skip
    good.update_yaxes(
        type="log",
        title_text="hours (log scale)",
        tickvals=[1, 2, 5, 10, 20, 50],
        ticktext=["1", "2", "5", "10", "20", "50"],
    )
    md.append("## 2 · The average that hides the tail\n")
    md.append(_pair(bad, good))
    md.append(
        f"**Why the left one misleads.** Repair times are right-skewed: most repairs are short and a few wait "
        f"days for spare parts. The mean of '{worst}' ({modes.loc[worst, 'mean']:.1f} h) describes almost no "
        f"real repair - its median is {modes.loc[worst, 'median']:.1f} h. Ranking modes by the mean ranks them "
        "by their outliers. **What the right one does:** shows the distribution, so the typical repair and "
        "the tail are both visible - and points the decision at the tail (spare parts), not at the technicians. "
        "MTTR stays a mean in the catalog for the availability identity, and is always shown next to the median.\n"
    )

    # 3 ------------------------------------------------------------ too many series
    fc = t["forecast"]
    top = fc.groupby("sku")["actual_units"].sum().nlargest(10).index
    w = (
        fc[fc["sku"].isin(top)]
        .pivot_table(index="week", columns="sku", values="actual_units", aggfunc="sum")
        .fillna(0)
    )
    w = w[w.index >= w.index.max() - pd.Timedelta(days=364)]
    ratio = w.tail(12).mean() / w.head(12).mean().where(lambda x: x > 0)
    star = ratio.idxmin()
    stopped = w[star].tail(8).sum() == 0
    last_sale = w.index[w[star] > 0].max()
    bad = go.Figure()
    for i, s in enumerate(w.columns):
        bad.add_trace(
            go.Scatter(
                x=w.index, y=w[s], name=s, mode="lines", line=dict(color=RAINBOW[i % 10], width=1.5)
            )
        )
    bad.update_layout(
        title=_plain_title("Weekly demand, top 10 SKUs"),
        showlegend=True,
        legend=dict(font=dict(size=9)),
    )
    good = go.Figure()
    for s in w.columns:
        if s != star:
            good.add_trace(go.Scatter(x=w.index, y=w[s], mode="lines", line=dict(color=theme.CONTEXT, width=1), showlegend=False,
                                      hovertemplate=f"{s}: %{{y:,.0f}}<extra></extra>"))  # fmt: skip
    good.add_trace(go.Scatter(x=w.index, y=w[star], mode="lines", line=dict(color=theme.HIGHLIGHT, width=2.5), showlegend=False,
                              hovertemplate=f"{star}: %{{y:,.0f}}<extra></extra>"))  # fmt: skip
    peak_week = w[star].idxmax()
    charts.annotate(good, peak_week, float(w[star].max()), f"SKU {star}", ay=-30)
    good.update_layout(title=theme.title(
        (f"SKU {star}, a top-10 seller, stopped selling after {last_sale:%B %Y} - its stock is now at risk"
         if stopped else f"SKU {star} lost {1 - ratio[star]:.0%} of its weekly demand in a year"),
        "Weekly units, top 10 SKUs; the other nine in grey for context", W))  # fmt: skip
    md.append("## 3 · Too many series\n")
    md.append(_pair(bad, good))
    md.append(
        "**Why the left one misleads.** Ten colours exceed what anyone can match to a legend, several hues are "
        "indistinguishable for colour-blind readers, and no line is more important than another - so the "
        "chart has no message. **What the right one does:** one highlighted series carries the message, the "
        "others stay as grey context, and the label sits on the line instead of in a legend. If every series "
        "matters, use small multiples instead.\n"
    )

    # 4 --------------------------------------------------------------------- pie vs bars
    counts = corr["failure_label"].value_counts()
    bad = go.Figure(
        go.Pie(
            labels=counts.index,
            values=counts.values,
            marker=dict(colors=RAINBOW),
            sort=False,
            textinfo="label",
        )
    )
    bad.update_layout(title=_plain_title("Failures by mode"), showlegend=False)
    good = charts.bar(
        counts.index, counts.values, conclusion="", subtitle="", highlight={counts.index[0]}, xformat=",.0f",
        text=[f"{n} ({pct(n / counts.sum())})" for n in counts.values],
    )  # fmt: skip
    good.update_layout(title=theme.title(
        f"{counts.index[0]} leads with {pct(counts.iloc[0] / counts.sum())}; {counts.index[1].lower()} is a clear second",
        "Corrective work orders by failure mode, sorted", W))  # fmt: skip
    good.update_xaxes(range=[0, counts.max() * 1.4])
    md.append("## 4 · The pie with too many slices\n")
    md.append(_pair(bad, good))
    md.append(
        f"**Why the left one misleads.** People compare angles and areas poorly; with {len(counts)} slices, "
        "the ranking of the middle modes is guesswork and the small slices vanish. **What the right one does:** "
        "sorted bars on a common baseline make the ranking and the gaps exact. A pie is acceptable only for two "
        "or three parts of a whole (the NPS bar in case 4 is the only part-to-whole chart on this site).\n"
    )

    # 5 ------------------------------------------------------------ traffic light without target
    ap = t["asset_periods"]
    av = e.compute_by("availability", ap, "asset_id").set_index("asset_id")["value"].sort_index()
    fleet = float(av.mean())
    rel = ["red" if x < fleet else "green" for x in av]
    bad = go.Figure(go.Scatter(x=list(av.index), y=[1] * len(av), mode="markers",
                               marker=dict(size=20, color=[theme.STATUS[s] for s in rel])))  # fmt: skip
    bad.update_layout(title=_plain_title("Machine status"))
    bad.update_yaxes(visible=False, range=[0.5, 1.5])
    bad.update_xaxes(showline=False, ticks="")
    target, amber = e.catalog["availability"].target, e.catalog["availability"].thresholds["amber"]
    status = [e.status("availability", x) for x in av]
    order = av.sort_values().index
    good = go.Figure(go.Bar(
        y=list(order), x=av[order], orientation="h",
        marker_color=[theme.STATUS[e.status("availability", av[m])] for m in order],
        text=[f"{theme.STATUS_ICON[e.status('availability', av[m])]} {pct(av[m], 1)}" for m in order],
        textposition="outside", cliponaxis=False))  # fmt: skip
    good.add_vrect(
        x0=amber, x1=target, fillcolor="rgba(250,178,25,0.12)", line_width=0, layer="below"
    )
    charts.add_target(good, target, f"Target {pct(target)}", axis="x")
    good.update_layout(title=theme.title(
        f"{status.count('red')} machines need action, {status.count('amber')} are close, {status.count('green')} are on target",
        f"Availability vs a {pct(target)} target; amber band {pct(amber)}-{pct(target)}; axis starts at 75%", W))  # fmt: skip
    good.update_xaxes(range=[0.75, 1.03], tickformat=".0%")
    good.update_yaxes(autorange="reversed")
    md.append("## 5 · The traffic light without a target\n")
    md.append(_pair(bad, good, height=420))
    md.append(
        f"**Why the left one misleads.** The colours compare each machine with the fleet average ({pct(fleet, 1)}), "
        "so about half of the fleet is red *by construction*, even if every machine met the target - and "
        "red/green dots carry no value, no target and no meaning for colour-blind readers. **What the right one "
        "does:** the status comes from the catalog's target and thresholds, the value is printed, the target and "
        "the amber band are drawn, and every colour travels with an icon (✓ ! ✕).\n"
    )

    # 6 ---------------------------------------------------------------------- dual axis
    tkm = tk.groupby("created_month").size()
    slam = e.compute_by(
        "sla_compliance", tk[tk["status"] == "resolved"], "resolved_month"
    ).set_index("resolved_month")["value"]
    bad = go.Figure()
    bad.add_trace(go.Bar(x=tkm.index, y=tkm.values, name="Tickets", marker_color=theme.CONTEXT))
    bad.add_trace(
        go.Scatter(
            x=slam.index,
            y=slam.values,
            name="SLA %",
            yaxis="y2",
            line=dict(color=theme.SECOND, width=3),
        )
    )
    bad.update_layout(
        title=_plain_title("Tickets and SLA"),
        yaxis2=dict(
            overlaying="y",
            side="right",
            range=[slam.min() - 0.005, slam.max() + 0.005],
            tickformat=".0%",
            showgrid=False,
        ),
    )
    fs = tk[tk["queue"].eq("Field Support")].groupby("created_month").size()
    others = tk[~tk["queue"].eq("Field Support")].groupby("created_month").size()
    idx_fs, idx_ot = fs / fs.iloc[:6].mean() * 100, others / others.iloc[:6].mean() * 100
    good = charts.line(
        idx_fs.index, idx_fs.values, conclusion="", subtitle="", name="Field Support", yformat=".0f",
        context={"Other queues": (idx_ot.index, idx_ot.values)},
    )  # fmt: skip
    good.update_layout(title=theme.title(
        f"Field Support demand is {idx_fs.iloc[-1]:.0f}% of its H1 level; the other queues stay near 100%",
        "Tickets created per month, indexed to the Jan-Jun average = 100 (one axis)", W))  # fmt: skip
    good.update_yaxes(rangemode="tozero")
    md.append("## 6 · Two y-axes on one chart\n")
    md.append(_pair(bad, good))
    md.append(
        "**Why the left one misleads.** The two scales are independent, so where the line crosses the bars is an "
        "arbitrary choice of axis ranges - it invents a correlation (or hides one). Total volume also mixes the "
        "queue that changed with three that did not. **What the right one does:** one axis, both series indexed "
        "to the same base, and the comparison that explains the SLA drop (case 1) made explicit. Show the SLA "
        "trend in its own chart next to it.\n"
    )

    md.append(
        "---\n\nThe rules behind the honest versions are listed on the [method page](method.md); the case pages "
        "apply them to every chart.\n"
    )
    return "\n".join(md)
