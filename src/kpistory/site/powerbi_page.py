"""Website page describing the Power BI layer (generated from the catalog)."""

from __future__ import annotations

from ..engine import Engine, format_threshold
from ..powerbi.export import DATA_URL, FORMAT, HOME_TABLE, RELATIONSHIPS, measure_name

REPO = "https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/blob/main"


def build(engine: Engine) -> str:
    c = engine.catalog
    md = [
        "# Power BI layer\n",
        '!!! warning "What is and is not done"\n'
        "    The Power BI files are **generated from the catalog but were not executed in Power BI Desktop** - Desktop "
        "does not run in the environment where this repository was built, so a PBIP/TMDL project could not be "
        "validated. Instead the repository ships the DAX measures, the star schema and a build checklist. "
        "Nothing on this page is a screenshot of a Power BI report.\n",
        "## What is generated\n",
        f"| File | Content |\n|---|---|\n"
        f"| [`powerbi/measures.dax`]({REPO}/powerbi/measures.dax) | All {len(c)} KPIs as DAX measures, ready for DAX query view, with an `EVALUATE` that returns every KPI in one row |\n"
        f"| [`powerbi/MODEL.md`]({REPO}/powerbi/MODEL.md) | Star schema: fact and dimension tables, columns and types, {len(RELATIONSHIPS)} relationships |\n"
        f"| [`powerbi/BUILD_CHECKLIST.md`]({REPO}/powerbi/BUILD_CHECKLIST.md) | Step-by-step assembly in Power BI Desktop, including a reconciliation step |\n"
        f"| [`powerbi/theme.json`]({REPO}/powerbi/theme.json) | The site's palette as a Power BI report theme |\n"
        f"| [`data/powerbi/*.csv`]({DATA_URL}/manifest.json) on this site | The model tables and `expected_values.csv` (Python results), rebuilt by GitHub Actions on every push - load them in Power BI with *Get data → Web* |\n",
        "## Why this proves the point of the repository\n",
        "The DAX below is not written for Power BI: it is stored in `kpis/catalog.yaml` next to the definition, "
        "the Python function and the SQL. Parameters such as the 7-day backlog limit are substituted from the "
        "catalog, so changing a rule changes all three implementations. The reconciliation step "
        "(`EVALUATE` vs `expected_values.csv`) checks that the DAX returns the same numbers as the tested Python engine.\n",
        "## Measures\n",
        "| Measure | Home table | Format | Target |",
        "|---|---|---|---|",
    ]
    md += [
        f"| [{measure_name(k)}](catalog/{k.id}.md) | {HOME_TABLE[k.input['table']]} | `{FORMAT[k.unit]}` | {format_threshold(k)} |"
        for k in c
    ]
    md.append("\n## Three examples\n")
    for kid in ("sla_compliance", "otif", "retention_rate"):
        k = c[kid]
        md.append(
            f"**{k.name}** - {k.question}\n\n```dax\n{measure_name(k)} =\n{k.dax_expression}\n```\n"
        )
    return "\n".join(md)
