"""Power BI layer, generated from the catalog.

Power BI Desktop cannot run in this repository's build environment, so a PBIP/TMDL
project could not be opened to prove it valid. Instead this module generates, from
kpis/catalog.yaml:

  powerbi/measures.dax        every KPI as a DAX measure, in DAX-query-view format
  powerbi/MODEL.md            the star schema: tables, columns, relationships
  powerbi/BUILD_CHECKLIST.md  the steps to assemble the model in Power BI Desktop
  powerbi/theme.json          the site's palette as a Power BI report theme
  powerbi/data/*.csv          the model tables (after `kpistory data`; not committed)
  powerbi/data/expected_values.csv  Python results to reconcile the DAX against
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import pandas as pd

from ..catalog import KPI, Catalog, load
from ..engine import format_threshold, format_value
from ..paths import POWERBI_DIR, PROCESSED_DIR
from ..viz import theme

PAGES_URL = "https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling"
DATA_URL = f"{PAGES_URL}/data/powerbi"

HEADER = "// GENERATED FROM kpis/catalog.yaml by `kpistory powerbi` - do not edit by hand.\n"

FORMAT = {
    "percent": "0.0%",
    "hours": '0.0 "h"',
    "days": '0.0 "d"',
    "times_per_year": '0.0"x"',
    "score": "+0;-0;0",
}


@dataclass
class Table:
    name: str
    source: str  # processed table it is exported from
    grain: str
    columns: dict[str, str]  # column -> type
    role: str = "fact"
    derive: dict[str, str] = field(
        default_factory=dict
    )  # new column -> source datetime column (date part)


MODEL: list[Table] = [
    Table("Tickets", "tickets", "one row per ticket", {
        "ticket_id": "text", "created_at": "datetime", "created_date": "date", "priority": "text", "queue": "text",
        "channel": "text", "status": "text", "first_response_hours": "decimal", "resolution_hours": "decimal",
        "sla_target_hours": "decimal", "within_sla": "boolean", "age_days": "decimal", "contacts": "integer",
        "reopened": "boolean"}, derive={"created_date": "created_at"}),
    Table("WorkOrders", "work_orders", "one row per work order", {
        "wo_id": "text", "asset_id": "text", "wo_type": "text", "planned": "boolean", "created_date": "date",
        "due_date": "date", "completed_at": "datetime", "repair_hours": "decimal", "labor_hours": "decimal",
        "failure_label": "text", "pm_on_time": "boolean"}, derive={"created_date": "created_at"}),
    Table("AssetPeriods", "asset_periods", "one row per machine and month", {
        "asset_id": "text", "month": "date", "operating_hours": "decimal", "scheduled_hours": "decimal",
        "unplanned_downtime_hours": "decimal", "failures": "integer"}),
    Table("OrderLines", "order_lines", "one row per order line", {
        "order_id": "text", "sku": "text", "order_date": "date", "promised_date": "date", "delivered_date": "date",
        "qty_ordered": "integer", "qty_shipped": "integer"}),
    Table("InventoryDaily", "inventory_daily", "one row per SKU and day", {
        "date": "date", "sku": "text", "on_hand_units": "decimal", "on_hand_value": "decimal",
        "demand_units": "decimal", "shipped_units": "decimal", "cogs_value": "decimal", "active": "boolean"}),
    Table("InventorySnapshot", "inventory_snapshot", "one row per SKU at the last date", {
        "sku": "text", "sku_group": "text", "on_hand_units": "decimal", "on_hand_value": "decimal",
        "days_since_last_movement": "integer"}),
    Table("Forecast", "forecast", "one row per SKU and week", {
        "sku": "text", "week": "date", "actual_units": "decimal", "forecast_units": "decimal"}),
    Table("Sales", "customer_sales", "one row per invoice line of an identified customer", {
        "invoice_id": "text", "invoice_date": "date", "customer_id": "text", "sku": "text", "quantity": "integer",
        "unit_price": "decimal", "revenue": "decimal", "country": "text"}, derive={"invoice_date": "invoice_date"}),
    Table("Survey", "survey", "one row per NPS response", {
        "response_id": "text", "customer_id": "text", "score": "integer", "responded_date": "date"},
        derive={"responded_date": "responded_at"}),
    Table("DQResults", "dq_results", "one row per dataset and data-quality dimension", {
        "dataset": "text", "label": "text", "dimension": "text", "passed": "integer", "total": "integer"}),
    Table("Customers", "customer_rfm", "one row per customer (RFM at the last date)", {
        "customer_id": "text", "rfm_segment": "text", "recency_days": "integer", "frequency": "integer",
        "monetary": "decimal", "r": "integer", "f": "integer", "m": "integer"}, role="dimension"),
    Table("Assets", "asset_periods", "one row per machine", {"asset_id": "text"}, role="dimension"),
    Table("Products", "inventory_snapshot", "one row per simulated SKU", {"sku": "text", "sku_group": "text"}, role="dimension"),
]  # fmt: skip

RELATIONSHIPS = [
    ("Date", "Date", "Tickets", "created_date"),
    ("Date", "Date", "WorkOrders", "created_date"),
    ("Date", "Date", "AssetPeriods", "month"),
    ("Date", "Date", "OrderLines", "order_date"),
    ("Date", "Date", "InventoryDaily", "date"),
    ("Date", "Date", "Forecast", "week"),
    ("Date", "Date", "Sales", "invoice_date"),
    ("Date", "Date", "Survey", "responded_date"),
    ("Customers", "customer_id", "Sales", "customer_id"),
    ("Customers", "customer_id", "Survey", "customer_id"),
    ("Assets", "asset_id", "WorkOrders", "asset_id"),
    ("Assets", "asset_id", "AssetPeriods", "asset_id"),
    ("Products", "sku", "OrderLines", "sku"),
    ("Products", "sku", "InventoryDaily", "sku"),
    ("Products", "sku", "InventorySnapshot", "sku"),
    ("Products", "sku", "Forecast", "sku"),
]

HOME_TABLE = {
    "tickets": "Tickets", "work_orders": "WorkOrders", "asset_periods": "AssetPeriods", "order_lines": "OrderLines",
    "inventory_daily": "InventoryDaily", "inventory_snapshot": "InventorySnapshot", "forecast": "Forecast",
    "sales": "Sales", "customer_rfm": "Sales", "survey": "Survey", "any": "DQResults",
}  # fmt: skip

# How to reproduce the Python value in Power BI (filter context the measure needs).
COMPARE_NOTE = {
    "retention_rate": "Matrix by 'Date'[Year-Quarter]; compare the last complete quarter with the case page",
    "revenue_at_risk_share": "Filter 'Date' to the 12 months ending on the last invoice date",
}


def measure_name(k: KPI) -> str:
    """Catalog name without characters that are awkward in DAX object names."""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 %-]", " ", k.name)).strip()


def _direction(k: KPI) -> str:
    return k.direction.replace("_", " ")


def measures_dax(catalog: Catalog) -> str:
    lines = [
        HEADER,
        "// Every KPI of the catalog as a DAX measure. Two ways to load them:",
        "//  1. Power BI Desktop > DAX query view: paste this file, run it, then use",
        "//     'Update model with changes' (or the 'Update model: Add new measure' CodeLens).",
        "//  2. Or create each measure by hand (Modeling > New measure) and paste its expression.",
        "// The EVALUATE at the end returns every KPI in one row - compare it with",
        "// powerbi/data/expected_values.csv, produced by the Python engine on the same data.",
        "",
        "DEFINE",
    ]
    for case, meta in catalog.cases.items():
        lines.append(f"    // ===== {meta['title']} =====")
        for k in catalog.for_case(case):
            table = HOME_TABLE[k.input["table"]]
            lines.append(
                f"    // {k.name} | {k.unit}, {_direction(k)} | target {format_threshold(k)} | owner: {k.owner}"
            )
            lines.append(f"    // Q: {k.question}")
            lines.append(f"    // Format string: {FORMAT[k.unit]}")
            body = "\n".join("        " + ln for ln in k.dax_expression.strip().splitlines())
            lines.append(f"    MEASURE {table}[{measure_name(k)}] =\n{body}")
            lines.append("")
    lines.append("EVALUATE")
    cols = ",\n".join(f'    "{k.id}", [{measure_name(k)}]' for k in catalog)
    lines.append(f"ROW (\n{cols}\n)")
    return "\n".join(lines) + "\n"


def model_md(catalog: Catalog) -> str:
    md = [
        "<!-- GENERATED FROM src/kpistory/powerbi/export.py by `kpistory powerbi` - do not edit by hand. -->",
        "# Power BI semantic model (star schema)\n",
        "The model the measures in `measures.dax` expect. Fact tables keep the grain of the Python tables, so "
        "a measure filtered by the same rows returns the same number as the engine. All tables are exported to "
        "`powerbi/data/*.csv` by `make data powerbi`.\n",
        "## Diagram\n",
        "```mermaid",
        "erDiagram",
    ]
    for one, one_col, many, many_col in RELATIONSHIPS:
        md.append(f'    {one} ||--o{{ {many} : "{one_col} = {many_col}"')
    md.append("```\n")
    md.append("## Tables\n")
    md.append("| Table | Role | Grain | Columns |")
    md.append("|---|---|---|---|")
    md.append(
        "| Date | dimension | one row per day | Date (date), Year, Quarter, Year-Quarter, Month, Year-Month, Week start |"
    )
    for t in MODEL:
        cols = ", ".join(f"{c} ({ty})" for c, ty in t.columns.items())
        md.append(f"| {t.name} | {t.role} | {t.grain} | {cols} |")
    md.append("\n## Relationships\n")
    md.append("All one-to-many, single direction (dimension filters fact), active.\n")
    md.append("| From (one) | To (many) |\n|---|---|")
    md += [f"| {a}[{ac}] | {b}[{bc}] |" for a, ac, b, bc in RELATIONSHIPS]
    md.append("\n## Measures by home table\n")
    md.append("| Measure | Home table | Format string | Target |")
    md.append("|---|---|---|---|")
    for k in catalog:
        md.append(
            f"| {measure_name(k)} | {HOME_TABLE[k.input['table']]} | `{FORMAT[k.unit]}` | {format_threshold(k)} |"
        )
    md.append(
        "\n## Notes\n\n"
        "- `Sales` holds identified customers only (the same rows as the Python `customer_sales` table); guest "
        "checkouts are measured in the data-quality case.\n"
        "- `within_sla`, `pm_on_time` and `active` are computed in Python with the catalog parameters and "
        "exported as columns, so the rule is written once.\n"
        "- Mark `Date` as a date table (Table tools > Mark as date table) - the retention measure uses `DATEADD`.\n"
    )
    return "\n".join(md)


def checklist(catalog: Catalog) -> str:
    names = "\n".join(
        f"- [ ] `{measure_name(k)}` ({HOME_TABLE[k.input['table']]}) - format `{FORMAT[k.unit]}`"
        for k in catalog
    )
    return f"""<!-- GENERATED by `kpistory powerbi` - do not edit by hand. -->
# Build checklist · Power BI Desktop

What exists in this folder was **generated from the catalog but never opened in Power BI Desktop**
(Desktop does not run in the environment where this repository was built). Follow these steps on
Windows to assemble the report; the measures and the model are ready, the pages are yours to design.

Everything except Power BI Desktop itself runs in the cloud: GitHub Actions downloads the data, computes
the tables and publishes them with the website. Nothing has to be installed or run on your PC besides Desktop.

## 1 · Get the data from the cloud (2 min)

- [ ] Open `{DATA_URL}/manifest.json` to see whether the last build used the real UCI files or plan B.
- [ ] The model tables are published at `{DATA_URL}/<Table>.csv`:
      {", ".join(["Date"] + [t.name for t in MODEL])}, plus `expected_values.csv`.
- [ ] Alternative: download the `powerbi-layer` artifact from the latest *Publish site* run in GitHub Actions.

## 2 · Load and type the tables (15 min)

- [ ] Get data > **Web** > `{DATA_URL}/Tickets.csv`, and the same for every table above
      (the URLs refresh on every push to `main`, so a scheduled refresh in Power BI Service also works).
- [ ] In Power Query set the column types listed in `MODEL.md` (dates as *Date*, booleans as *True/False*).
- [ ] Load `Date.csv`, then Table tools > **Mark as date table** on `Date[Date]`.

## 3 · Relationships (10 min)

- [ ] Model view: create the {len(RELATIONSHIPS)} one-to-many relationships listed in `MODEL.md`
      (single direction, dimension → fact). Delete any relationship Desktop auto-detected that is not in the list.

## 4 · Measures (10 min)

- [ ] Open **DAX query view**, paste `measures.dax`, run it. The result row shows all {len(catalog)} KPIs.
- [ ] Use **Update model with changes** to add the measures to the model.
- [ ] Set each measure's format string (also written in `measures.dax` above each measure):
{names}

## 5 · Reconcile with Python (5 min) - do not skip

- [ ] Compare the EVALUATE row with `powerbi/data/expected_values.csv`. Every KPI should match to the
      decimal, except the ones whose `compare_in` column asks for a filter context (retention, revenue at risk).
- [ ] If a value differs, the usual causes are: a column typed as text instead of number/date, a missing
      relationship, or the `Date` table not marked as a date table.

## 6 · Theme and pages (your design)

- [ ] View > Themes > Browse for themes > `powerbi/theme.json` (same palette as the website).
- [ ] Build one page per case with the same story order as the site: KPI cards (value, target, status icon) →
      the finding visual → a table with the action list. Use the chart type recommended in the catalog
      for each KPI (it is written on every KPI page of the site).
- [ ] Save as **Power BI project (.pbip)** so the model is stored as text (TMDL) and can be committed and diffed.
"""


def theme_json() -> str:
    return json.dumps(
        {
            "name": "KPI catalog & storytelling",
            "dataColors": [
                theme.HIGHLIGHT,
                theme.SECOND,
                theme.THIRD,
                theme.CONTEXT_DARK,
                theme.CONTEXT,
            ],
            "background": "#FFFFFF",
            "foreground": theme.INK,
            "tableAccent": theme.HIGHLIGHT,
            "good": theme.STATUS["green"],
            "neutral": theme.STATUS["amber"],
            "bad": theme.STATUS["red"],
            "maximum": theme.SEQUENTIAL[-1],
            "center": theme.SEQUENTIAL[3],
            "minimum": theme.SEQUENTIAL[0],
            "textClasses": {
                "title": {"fontFace": "Segoe UI Semibold", "fontSize": 14, "color": theme.INK},
                "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": theme.INK_2},
            },
        },
        indent=2,
    )


def _date_table(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    starts, ends = [], []
    for t in MODEL:
        df = tables.get(t.source)
        if df is None:
            continue
        for col, ty in t.columns.items():
            src = t.derive.get(col, col)
            if ty == "date" and src in df.columns:
                s = pd.to_datetime(df[src]).dropna()
                if len(s):
                    starts.append(s.min())
                    ends.append(s.max())
    days = pd.date_range(min(starts).normalize(), max(ends).normalize(), freq="D")
    return pd.DataFrame(
        {
            "Date": days.date,
            "Year": days.year,
            "Quarter": "Q" + days.quarter.astype(str),
            "Year-Quarter": days.year.astype(str) + "-Q" + days.quarter.astype(str),
            "Month": days.month,
            "Year-Month": days.strftime("%Y-%m"),
            "Week start": (days - pd.to_timedelta(days.dayofweek, unit="D")).date,
        }
    )


def export_data(catalog: Catalog) -> None:
    from ..data.pipeline import load_tables
    from ..engine import Engine
    from ..site.current import current_values

    tables, manifest = load_tables()
    tables = dict(tables)
    tables["customer_rfm"] = tables["customer_rfm"].rename(columns={"segment": "rfm_segment"})
    out = POWERBI_DIR / "data"
    out.mkdir(parents=True, exist_ok=True)
    for t in MODEL:
        df = tables[t.source].copy()
        for col, src in t.derive.items():
            df[col] = pd.to_datetime(df[src]).dt.date
        df = df[list(t.columns)]
        if t.role == "dimension":
            df = df.drop_duplicates(subset=list(t.columns)[0])
        for col, ty in t.columns.items():
            if ty == "date" and col not in t.derive:
                df[col] = pd.to_datetime(df[col]).dt.date
            elif ty == "datetime":
                df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
        df.to_csv(out / f"{t.name}.csv", index=False)
    _date_table(tables).to_csv(out / "Date.csv", index=False)
    current = current_values(
        tables
        | {"customer_rfm": tables["customer_rfm"].rename(columns={"rfm_segment": "segment"})},
        Engine(catalog),
    )
    rows = [
        {
            "kpi_id": k.id,
            "measure": measure_name(k),
            "python_value": current.get(k.id),
            "formatted": format_value(k, current[k.id]) if k.id in current else "",
            "compare_in": COMPARE_NOTE.get(k.id, "No filters (whole model)"),
        }
        for k in catalog
    ]
    pd.DataFrame(rows).to_csv(out / "expected_values.csv", index=False)
    print(
        f"  Power BI data: {len(MODEL) + 1} tables -> {out} (source mode: {manifest['source_mode']})"
    )


def export() -> None:
    catalog = load()
    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    (POWERBI_DIR / "measures.dax").write_text(measures_dax(catalog), encoding="utf-8")
    (POWERBI_DIR / "MODEL.md").write_text(model_md(catalog), encoding="utf-8")
    (POWERBI_DIR / "BUILD_CHECKLIST.md").write_text(checklist(catalog), encoding="utf-8")
    (POWERBI_DIR / "theme.json").write_text(theme_json() + "\n", encoding="utf-8")
    print(f"  Power BI layer: {len(catalog)} measures, model, checklist, theme -> {POWERBI_DIR}")
    if (PROCESSED_DIR / "manifest.json").exists():
        export_data(catalog)
