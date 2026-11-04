"""Case 5 page - Data quality as a KPI."""

from __future__ import annotations

import pandas as pd

from ..data.quality import load_rules
from ..engine import Engine
from ..formulas.data_quality import timeliness_counts
from ..viz import charts
from .common import Tile, monitoring_table, pct, question, source_note, tiles

DIMS = ["completeness", "uniqueness", "validity", "timeliness"]


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    dq, cols, rules_df = t["dq_results"], t["dq_columns"], t["dq_rules"]
    rules = load_rules()
    measured = dq[dq["total"] > 0]
    below = measured[measured["status"] != "green"]
    pooled = {
        d: measured[measured["dimension"].eq(d)]["passed"].sum()
        / measured[measured["dimension"].eq(d)]["total"].sum()
        for d in DIMS
    }

    md = [
        "# Case 5 · Data quality as a KPI\n",
        source_note(manifest, ["tickets", "work_orders", "process_data", "transactions", "survey"]),
    ]
    md.append(
        "## Context\n\n"
        "Cases 1-4 computed 24 KPIs on five datasets. Each of those KPIs silently assumes the data is complete, "
        "unique, valid and on time. This case measures those assumptions with the same discipline as any other "
        "KPI: a catalog definition, a target, an owner and a rule file "
        "([`kpis/dq_rules.yaml`](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/blob/main/kpis/dq_rules.yaml)) "
        "that works as a small **data contract** per dataset. It is the bridge between KPI design and data "
        "governance: every rule has an owner who fixes it at the source.\n\n"
    )
    md.append(
        "## Question\n\n"
        + question(
            "Can we trust the data behind cases 1-4 - and which defect changes a business KPI?"
        )
    )
    md.append("## KPIs · landing data, pooled over all datasets\n\n")
    md.append(
        tiles(
            e,
            [
                Tile(
                    f"dq_{d}",
                    pooled[d],
                    f"{len(measured[measured['dimension'].eq(d)])} datasets measured",
                )
                for d in DIMS
            ],
        )
    )
    md.append(
        "Pooled figures are weighted by rows (the transaction log dominates them), so the per-dataset grid "
        "below is the view that matters.\n\n"
    )

    md.append("## Finding\n\n")
    matrix = dq.pivot(index="label", columns="dimension", values="value")[DIMS]
    status = dq.pivot(index="label", columns="dimension", values="status")[DIMS]
    order = [rules[k]["label"] for k in rules]
    matrix, status = matrix.reindex(order), status.reindex(order)
    matrix.columns = status.columns = [d.capitalize() for d in DIMS]
    worst = measured.sort_values("value").iloc[0]
    fig = charts.status_heatmap(
        matrix, status,
        conclusion=f"{len(below)} of {len(measured)} measurable checks are below target; the weakest is "
        f"{worst['dimension']} of {worst['label'].split(' (')[0].lower()} ({pct(worst['value'], 1)})",
        subtitle="Four data-quality KPIs per landing dataset - colour = status against the catalog target, "
        "never the raw value",
    )  # fmt: skip
    md.append(
        charts.to_html(
            fig,
            height=380,
            table=dq[["label", "dimension", "passed", "total", "value", "status"]].round(4),
        )
    )

    trx = cols[cols["dataset"].eq("transactions")].sort_values("value")
    weakest_col = trx.iloc[0]
    anon_rev = 1 - t["customer_sales"]["revenue"].sum() / t["sales"]["revenue"].sum()
    fig = charts.bar(
        trx["column"], trx["value"],
        conclusion=f"'{weakest_col['column']}' is empty on {pct(1 - weakest_col['value'])} of sales lines - "
        f"retention and RFM never see {pct(anon_rev)} of revenue",
        subtitle="Completeness of each required column of the sales transactions (landing data)",
        highlight={weakest_col["column"]}, text=[pct(x, 1) for x in trx["value"]],
    )  # fmt: skip
    fig.update_xaxes(range=[0, 1.12])
    md.append(charts.to_html(fig, height=320))
    md.append(
        "Dataset-level completeness of the transactions looks acceptable "
        f"({pct(matrix.loc[rules['transactions']['label'], 'Completeness'], 1)}) because six columns are averaged - "
        "the exact misreading listed in the catalog. One column carries the whole problem.\n\n"
    )

    r = rules_df[rules_df["failed_rows"] > 0].assign(share=lambda d: d["failed_rows"] / d["rows"])
    r = r.assign(
        label=r["dataset"].map({k: v["label"].split(" (")[0] for k, v in rules.items()})
        + ": "
        + r["rule"]
    )
    r = r.sort_values("failed_rows", ascending=False).head(8)
    top = r.iloc[0]
    fig = charts.bar(
        r["label"], r["failed_rows"],
        conclusion=f"The biggest validity issue is '{top['rule']}' ({int(top['failed_rows']):,} rows) - "
        "each bar is a fix request for a source-system owner",
        subtitle="Rows failing each validity rule (rules with at least one failure)",
        highlight={top["label"]}, xformat=",.0f", text=[f"{int(n):,} ({pct(s, 1)})" for n, s in zip(r["failed_rows"], r["share"], strict=True)],
    )  # fmt: skip
    fig.update_xaxes(range=[0, r["failed_rows"].max() * 1.3])
    md.append(charts.to_html(fig, height=360))

    wo = t["landing_work_orders"].drop_duplicates("wo_id")
    tcfg = rules["work_orders"]["timeliness"]
    per_asset = pd.Series(
        {a: (lambda p, n: p / n if n else float("nan"))(*timeliness_counts(g.dropna(subset=[tcfg["event_col"]]), **tcfg))
         for a, g in wo.groupby("asset_id")}
    ).sort_values()  # fmt: skip
    late = [a for a in per_asset.index if e.status("dq_timeliness", per_asset[a]) == "red"]
    rest = per_asset.drop(late)
    fig = charts.bar(
        per_asset.index, per_asset.values,
        conclusion=(f"{', '.join(late)} log only {pct(per_asset[late].mean())} of work orders within 24 h "
                    f"(every other machine: at least {pct(rest.min())}) - their maintenance KPIs lag by days") if late else
                   "Every machine logs its work orders on time",
        subtitle="Work orders recorded in the system within 24 h of completion, by machine",
        highlight=set(late), text=[pct(x) for x in per_asset.values],
    )  # fmt: skip
    charts.add_target(
        fig,
        e.catalog["dq_timeliness"].target,
        f"Target {pct(e.catalog['dq_timeliness'].target)}",
        axis="x",
    )
    fig.update_xaxes(range=[0, 1.12])
    md.append(charts.to_html(fig, height=380))
    not_measurable = dq[dq["total"].eq(0)]["label"].tolist()
    if not_measurable:
        md.append(
            f"**Not measurable:** {', '.join(not_measurable)} carry no load timestamp, so their timeliness cannot "
            "be computed. The grid says so instead of showing a made-up 100% - a missing audit column is itself a finding.\n\n"
        )

    md.append(
        "## Decision\n\n"
        "1. **Make the customer id mandatory, or reward it** (loyalty account, faster checkout). It is the one "
        "defect that changes business KPIs: retention, repeat rate and RFM are computed on identified customers only.\n"
        "2. **De-duplicate at ingestion** with the business keys of `dq_rules.yaml`; duplicates inflate ticket "
        "and work-order counts in every service and maintenance KPI.\n"
        + (
            f"3. **Mobile work-order logging for the {', '.join(late)} crews** - paper work orders entered days later "
            "make MTTR and PM compliance lag and hide the night shift's real performance.\n"
            if late
            else ""
        )
        + "4. **Add a load timestamp to every source** so timeliness can be measured everywhere.\n"
        "5. **Publish the grid with owners**: each red cell has a named data steward and a due date.\n\n"
    )
    md.append(
        "## How we keep measuring\n\n"
        + monitoring_table(
            e,
            [
                ("dq_completeness", "Every load, per required column", "Required column below 95%"),
                ("dq_uniqueness", "Every load", "Any duplicate business key"),
                ("dq_validity", "Every load, per rule", "Rule failure rate above 2%"),
                ("dq_timeliness", "Daily, per source", "Below 90% within the window"),
            ],
        )  # fmt: skip
        + "The checks run in the same pipeline that computes the business KPIs, so a red data-quality cell is "
        "visible before anyone reads a business number built on it.\n"
    )
    return "\n".join(md)
