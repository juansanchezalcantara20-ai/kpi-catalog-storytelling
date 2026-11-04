"""Case 2 page - Maintenance & asset reliability."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..data.maintenance import FAILURE_LABEL, N_MACHINES, RUN_HOURS
from ..engine import Engine
from ..viz import charts, theme
from .common import Tile, monitoring_table, pct, question, source_note, tiles

TOOL_CHANGE_AT = 190  # minutes; proposed condition-based tool change
LONG_REPAIR_H = 12


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    runs, wo, ap = t["runs"], t["work_orders"], t["asset_periods"]
    corr = wo[wo["wo_type"].eq("corrective")]
    a_target = e.catalog["availability"].target

    v = {
        "availability": e.compute("availability", ap),
        "mtbf": e.compute("mtbf", ap),
        "mttr": e.compute("mttr", wo),
        "pm_compliance": e.compute("pm_compliance", wo),
        "planned_work_share": e.compute("planned_work_share", wo),
    }
    by_asset = pd.DataFrame(
        {
            "availability": e.compute_by("availability", ap, "asset_id").set_index("asset_id")["value"],
            "mtbf": e.compute_by("mtbf", ap, "asset_id").set_index("asset_id")["value"],
            "mttr": e.compute_by("mttr", wo[wo["wo_type"].eq("corrective")], "asset_id").set_index("asset_id")["value"],
            "pm_compliance": e.compute_by("pm_compliance", wo[wo["wo_type"].eq("preventive")], "asset_id").set_index("asset_id")["value"],
            "failures": ap.groupby("asset_id")["failures"].sum(),
            "downtime_h": ap.groupby("asset_id")["unplanned_downtime_hours"].sum(),
        }
    )  # fmt: skip
    av_sorted = by_asset.sort_values("availability")
    below = av_sorted[av_sorted["availability"] < a_target]
    amber = e.catalog["availability"].thresholds["amber"]
    worst_ids = list(av_sorted.index[av_sorted["availability"] < amber]) or list(
        av_sorted.index[:1]
    )
    worst_share_down = by_asset.loc[worst_ids, "downtime_h"].sum() / by_asset["downtime_h"].sum()

    md = [
        "# Case 2 · Maintenance & asset reliability\n",
        source_note(manifest, ["process_data", "work_orders"]),
    ]
    md.append(
        "## Context\n\n"
        f"A plant runs **{N_MACHINES} machines** in two shifts. The process data has one record per "
        f"{RUN_HOURS:.0f}-hour production run with the machine's temperatures, speed, torque, tool wear and "
        f"failure flags ({len(runs):,} runs in 2024). Every failure opens a corrective work order; each machine "
        "also has a weekly preventive maintenance (PM) routine.\n\n"
    )
    md.append("## Question\n\n" + question(
        "Why is availability below target - is it a reliability problem (we fail too often) or a repair "
        "problem (we take too long to fix)? And what can we plan instead of react to?"
    ))  # fmt: skip
    md.append("## KPIs · 2024\n\n")
    md.append(
        tiles(
            e,
            [
                Tile(
                    "availability",
                    v["availability"],
                    f"{len(below)} of {N_MACHINES} machines below target",
                ),
                Tile("mtbf", v["mtbf"], f"{int(ap['failures'].sum())} failures"),
                Tile("mttr", v["mttr"], f"median {corr['repair_hours'].median():.1f} h"),
                Tile("pm_compliance", v["pm_compliance"], "weekly PM, 3-day tolerance"),
                Tile("planned_work_share", v["planned_work_share"], "share of labour hours"),
            ],
        )
    )
    md.append(
        "Availability is the outcome operations feels. It decomposes into **MTBF** (how often we fail) and "
        "**MTTR** (how long we are down per failure): availability ≈ MTBF / (MTBF + MTTR). PM compliance and "
        "planned share are the **leading** side: they move before failures do.\n\n"
    )

    md.append("## Finding\n\n")
    names = ", ".join(worst_ids)
    fig = charts.bar(
        av_sorted.index, av_sorted["availability"],
        conclusion=f"{len(worst_ids)} of {N_MACHINES} machines are below {pct(amber)} and carry "
        f"{pct(worst_share_down)} of all unplanned downtime",
        subtitle=f"Availability by machine, 2024 (axis starts at 75%) - target {pct(a_target)}",
        highlight=set(worst_ids), text=[pct(x, 1) for x in av_sorted["availability"]],
    )  # fmt: skip
    charts.add_target(fig, a_target, f"Target {pct(a_target)}", axis="x")
    fig.update_xaxes(range=[0.75, 1.0])
    md.append(charts.to_html(fig, height=420, table=by_asset.reset_index().round(3)))
    md.append(
        "*Note: this bar chart does not start at zero on purpose - all machines are between 75% and 100% and the "
        "decision is about the gap to target; the axis start is stated in the subtitle.*\n\n"
    )

    med_mtbf, med_mttr = by_asset["mtbf"].median(), by_asset["mttr"].median()
    # Classify each low-availability machine by which side of the identity is worse than the fleet.
    gap_mtbf = by_asset["mtbf"] / med_mtbf  # < 1 = fails more often than the median machine
    gap_mttr = by_asset["mttr"] / med_mttr  # > 1 = slower to repair than the median machine
    reliability = [m for m in worst_ids if 1 / gap_mtbf[m] >= gap_mttr[m]]
    repair = [m for m in worst_ids if m not in reliability]
    parts = []
    if reliability:
        parts.append(
            f"{', '.join(reliability)} fail{'s' if len(reliability) == 1 else ''} far more often"
        )
    if repair:
        parts.append(f"{', '.join(repair)} take{'s' if len(repair) == 1 else ''} longer to repair")
    diagnosis = (
        "; ".join(parts) + " - two different problems"
        if reliability and repair
        else "; ".join(parts)
    )
    fig = go.Figure()
    colors = [theme.HIGHLIGHT if m in worst_ids else theme.CONTEXT_DARK for m in by_asset.index]
    fig.add_trace(go.Scatter(
        x=by_asset["mtbf"], y=by_asset["mttr"], mode="markers+text", text=by_asset.index, textposition="top center",
        marker=dict(size=13, color=colors, line=dict(color=theme.SURFACE, width=2)), textfont=dict(color=theme.INK_2),
        hovertemplate="%{text}<br>MTBF %{x:.0f} h<br>MTTR %{y:.1f} h<extra></extra>"))  # fmt: skip
    fig.add_vline(x=med_mtbf, line=dict(color=theme.AXIS, width=1))
    fig.add_hline(y=med_mttr, line=dict(color=theme.AXIS, width=1))
    for x, y, txt, xa, ya in [
        (by_asset["mtbf"].min(), by_asset["mttr"].max(), "fails often, slow to fix", "left", "top"),
        (
            by_asset["mtbf"].max(),
            by_asset["mttr"].min(),
            "reliable, quick to fix",
            "right",
            "bottom",
        ),
    ]:
        fig.add_annotation(
            x=x,
            y=y,
            text=txt,
            showarrow=False,
            xanchor=xa,
            yanchor=ya,
            font=dict(color=theme.MUTED, size=11),
        )
    fig.update_layout(title=theme.title(
        diagnosis,
        "Each dot is a machine: MTBF (h, right is better) vs MTTR (h, lower is better); lines = fleet medians"))  # fmt: skip
    fig.update_xaxes(
        title_text="MTBF (hours)", rangemode="normal", showgrid=True, gridcolor=theme.GRID
    )
    fig.update_yaxes(title_text="MTTR (hours)", rangemode="normal")
    md.append(charts.to_html(fig, height=420))

    modes = corr["failure_label"].value_counts()
    top_mode = modes.index[0]
    tool_related = corr["failure_mode"].isin(["TWF", "OSF"]).mean()
    fig = charts.bar(
        modes.index, modes.values,
        conclusion=f"{top_mode} is the first failure mode ({pct(modes.iloc[0] / modes.sum())}); "
        f"tool-related modes add {pct(tool_related)}",
        subtitle="Corrective work orders by failure mode, 2024",
        highlight={top_mode, FAILURE_LABEL["TWF"], FAILURE_LABEL["OSF"]}, xformat=",.0f",
        text=[f"{n}" for n in modes.values],
    )  # fmt: skip
    md.append(charts.to_html(fig, height=320))

    wear = runs.assign(bucket=(runs["Tool wear [min]"] // 25 * 25).clip(upper=225))
    rate = wear.groupby("bucket")["failure_mode"].apply(lambda s: s.notna().mean())
    labels = [f"{int(b)}-{int(b) + 24}" if b < 225 else "225+" for b in rate.index]
    hi, lo = wear[wear["Tool wear [min]"] >= 200], wear[wear["Tool wear [min]"] < 200]
    ratio = hi["failure_mode"].notna().mean() / lo["failure_mode"].notna().mean()
    fig = charts.bar(
        labels, rate.values,
        conclusion=f"A run with more than 200 min of tool wear is {ratio:.1f}x as likely to end in a failure",
        subtitle="Share of runs ending in a failure, by tool wear at the start of the run (minutes)",
        highlight={lab for lab, b in zip(labels, rate.index, strict=True) if b >= 200},
        horizontal=False, xformat=".1%", text=[pct(x, 1) for x in rate.values],
    )  # fmt: skip
    fig.update_xaxes(title_text="tool wear (min)")
    md.append(charts.to_html(fig, height=360))

    fail_runs = runs[
        runs["failure_mode"].isin(["TWF", "OSF"]) & (runs["Tool wear [min]"] >= TOOL_CHANGE_AT)
    ]
    n_avoid = len(fail_runs)
    avoid_hours = (
        n_avoid * corr.loc[corr["failure_mode"].isin(["TWF", "OSF"]), "repair_hours"].median()
    )

    mean, median = corr["repair_hours"].mean(), corr["repair_hours"].median()
    long_share = (
        corr.loc[corr["repair_hours"] > LONG_REPAIR_H, "repair_hours"].sum()
        / corr["repair_hours"].sum()
    )
    long_n = int((corr["repair_hours"] > LONG_REPAIR_H).sum())
    fig = go.Figure(go.Histogram(x=corr["repair_hours"], xbins=dict(start=0, size=1), marker_color=theme.CONTEXT,
                                 hovertemplate="%{x} h: %{y} repairs<extra></extra>"))  # fmt: skip
    for x, label, color, pos in ((median, f"median {median:.1f} h", theme.INK_2, "top left"),
                                 (mean, f"mean = MTTR {mean:.1f} h", theme.HIGHLIGHT, "top right")):  # fmt: skip
        fig.add_vline(
            x=x,
            line=dict(color=color, width=2),
            annotation=dict(text=label, font=dict(color=color)),
            annotation_position=pos,
        )
    fig.add_annotation(x=corr["repair_hours"].quantile(0.97), y=3, text=f"{long_n} repairs > {LONG_REPAIR_H} h (waiting for parts)",
                       showarrow=True, arrowhead=0, ax=0, ay=-60, font=dict(color=theme.INK))  # fmt: skip
    fig.update_layout(title=theme.title(
        f"MTTR is {mean:.1f} h, but the typical repair takes {median:.1f} h: {long_n} waits for parts "
        f"carry {pct(long_share)} of all repair hours",
        "Corrective work orders by repair duration (1-hour bins)"))  # fmt: skip
    fig.update_xaxes(title_text="repair hours")
    fig.update_yaxes(title_text="work orders")
    md.append(charts.to_html(fig, height=380))

    pm = by_asset["pm_compliance"].sort_values()
    pm_red = [m for m in pm.index if e.status("pm_compliance", pm[m]) == "red"]
    pm_rest = pm.drop(pm_red)
    fig = charts.bar(
        pm.index, pm.values,
        conclusion=(f"The crews of {', '.join(pm_red)} complete only {pct(pm[pm_red].mean())} of PMs on time; "
                    f"the rest {pct(pm_rest.min())}-{pct(pm_rest.max())}") if pm_red else "Every crew completes its PMs on time",
        subtitle="Preventive maintenance done within 3 days of the due date, by machine, 2024",
        highlight=set(pm_red), text=[pct(x) for x in pm.values],
    )  # fmt: skip
    charts.add_target(
        fig,
        e.catalog["pm_compliance"].target,
        f"Target {pct(e.catalog['pm_compliance'].target)}",
        axis="x",
    )
    fig.update_xaxes(range=[0, 1.1])
    md.append(charts.to_html(fig, height=400))

    worst_mode = corr[corr["asset_id"].isin(worst_ids)]["failure_label"].value_counts()
    rel_modes = corr[corr["asset_id"].isin(reliability)]["failure_label"].value_counts()
    rel_mode = rel_modes.index[0] if len(rel_modes) else worst_mode.index[0]
    md.append(
        f"**Reading it together.** Low availability has two different causes: {diagnosis.split(' - ')[0]}. "
        f"Across {names} the dominant failure mode is **{worst_mode.index[0]}** "
        f"({pct(worst_mode.iloc[0] / worst_mode.sum())} of their failures). Fleet-wide, tool wear is the "
        "clearest controllable driver: failure risk jumps after 200 minutes. MTTR looks worse than the typical "
        "repair because of a few long waits for spare parts. "
        + (f"PM lateness is concentrated in two crews ({', '.join(pm_red)}). " if pm_red else "")
        + "In the plan B data, PM lateness does not cause failures (an assumption of the generator); "
        "the page does not claim that link.\n\n"
    )

    md.append(
        "## Decision\n\n"
        f"1. **Condition-based tool change at {TOOL_CHANGE_AT} min of wear.** In 2024 it would have turned "
        f"**{n_avoid} unplanned tool-wear / overstrain failures** (about {avoid_hours:.0f} h of downtime at the "
        "median repair time) into planned tool changes - and raised the planned-work share.\n"
        + (f"2. **Root-cause {rel_mode.lower()} failures on {', '.join(reliability)}** before anything else: "
           "a machine-specific reliability problem that more technicians would not fix.\n" if reliability else "")
        + (f"   For {', '.join(repair)}, review the long repairs one by one (parts, skills, access).\n" if repair else "")
        +
        f"3. **Stock the critical spare parts** behind the {long_n} long repairs; the target is MTTR closer to "
        f"the {median:.1f} h median.\n"
        + (f"4. **Re-plan the PM routine of the {', '.join(pm_red)} crews** (night shift) - same weekly PM, "
           "scheduled inside their shift.\n\n" if pm_red else "\n")
    )  # fmt: skip
    md.append(
        "## How we keep measuring\n\n"
        + monitoring_table(
            e,
            [
                (
                    "pm_compliance",
                    "Weekly, per crew (leading)",
                    "Below 80% for a crew - re-plan the week",
                ),
                ("planned_work_share", "Monthly", "Below 65% - review reactive work orders"),
                (
                    "mtbf",
                    "Monthly per machine, 3-month rolling",
                    "Machine in the bottom 2 for 2 months",
                ),
                (
                    "mttr",
                    "Monthly, with median and longest repairs",
                    "Any repair > 12 h - check spare parts",
                ),
                ("availability", "Monthly per machine", "Below 95% - open a reliability review"),
            ],
        )
        + "Tool wear at failure is tracked as a diagnostic: after the policy change, no failure should "
        f"happen above {TOOL_CHANGE_AT} min.\n"
    )
    return "\n".join(md)
