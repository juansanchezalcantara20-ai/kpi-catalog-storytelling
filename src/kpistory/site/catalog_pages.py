"""KPI catalog pages: an index plus one page per KPI, generated from catalog.yaml."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import pandas as pd

from ..catalog import KPI
from ..engine import Engine, format_threshold, format_value
from ..formulas import REGISTRY
from ..paths import TESTS_DIR
from ..viz import theme

DIRECTION = {
    "higher_is_better": "Higher is better ↑",
    "lower_is_better": "Lower is better ↓",
    "target_range": "Inside a band ↔ (too high and too low are both bad)",
}
UNIT = {
    "percent": "%",
    "hours": "hours",
    "days": "days",
    "times_per_year": "times per year",
    "score": "score (-100 to +100)",
}


def _hand_examples() -> dict:
    spec = importlib.util.spec_from_file_location("hand_examples", TESTS_DIR / "hand_examples.py")
    if spec is None or spec.loader is None or not (TESTS_DIR / "hand_examples.py").exists():
        return {}
    module = importlib.util.module_from_spec(spec)
    sys.modules["hand_examples"] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module.BY_ID


def index_page(engine: Engine, current: dict[str, float]) -> str:
    md = [
        "# KPI catalog\n",
        "Generated from [`kpis/catalog.yaml`](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/blob/main/kpis/catalog.yaml) - "
        "the single source of truth for the Python engine, the SQL reference queries and the Power BI measures. "
        f"**{len(engine.catalog)} KPIs** in {len(engine.catalog.cases)} domains. Every KPI page shows its definition, "
        "how to read it, the common misreadings, its DAX and SQL, the Python function and a worked example "
        "taken from the test suite.\n",
    ]
    for case, meta in engine.catalog.cases.items():
        md.append(f"\n## {meta['title']}\n")
        md.append("| KPI | Business question | Direction | Target | Owner | Current |")
        md.append("|---|---|---|---|---|---|")
        for k in engine.catalog.for_case(case):
            value = current.get(k.id, float("nan"))
            status = engine.status(k.id, value)
            cur = (
                f"{theme.STATUS_ICON[status]} {format_value(k, value)}" if k.id in current else "–"
            )
            md.append(
                f"| [{k.name}]({k.id}.md) | {k.question} | {DIRECTION[k.direction].split(' (')[0]} | "
                f"{format_threshold(k).split(' (')[0]} | {k.owner} | {cur} |"
            )
    md.append(
        "\n*Current* = value on the full dataset of the case (illustrative). Status icons: ✓ on target, ! watch, ✕ act.\n"
    )
    return "\n".join(md)


def kpi_page(engine: Engine, k: KPI, current: float | None, examples: dict, cases: set[str]) -> str:
    md = [f"# {k.name}\n", f'<p class="story-question">{k.question}</p>\n']
    if current is not None:
        status = engine.status(k.id, current)
        md.append(
            f"**Current value ({k.case} case data):** {format_value(k, current)} - "
            f"{theme.STATUS_ICON[status]} {theme.STATUS_TEXT[status]}."
            + (f" [Open the case](../cases/{k.case}.md)." if k.case in cases else "")
            + "\n"
        )
    md.append("| Field | Value |\n|---|---|")
    rows = [
        ("Definition", k.definition),
        ("Formula", f"`{k.formula}`"),
        ("Unit", UNIT[k.unit]),
        ("Granularity", k.granularity),
        ("Direction", DIRECTION[k.direction]),
        ("Target and thresholds", format_threshold(k)),
        ("Parameters", ", ".join(f"`{p} = {v}`" for p, v in k.params.items()) or "–"),
        ("Owner", k.owner),
        ("Source", k.source),
        (
            "Input",
            f"table `{k.input['table']}`, columns "
            + (", ".join(f"`{c}`" for c in k.input["columns"]) or "per `kpis/dq_rules.yaml`"),
        ),
        ("Recommended chart", f"**{k.chart['type']}** - {k.chart['why']}"),
        (
            "Related KPIs",
            ", ".join(f"[{engine.catalog[r].name}]({r}.md)" for r in k.related) or "–",
        ),
    ]
    md += [f"| {a} | {b.replace('|', '/')} |" for a, b in rows]
    md.append(f"\n## How to read it\n\n{k.how_to_read}\n")
    md.append("## Common misreadings\n")
    md += [f"- {m}" for m in k.misreadings]
    ex = examples.get(k.id)
    if ex is not None:
        table = ex.table.copy()
        for col in table.columns:
            if pd.api.types.is_datetime64_any_dtype(table[col]):
                table[col] = (
                    table[col].dt.strftime("%Y-%m-%d %H:%M").str.replace(" 00:00", "", regex=False)
                )
        md.append("\n## Worked example (from the test suite)\n")
        md.append(table.to_markdown(index=False) if _has_tabulate() else _md_table(table))
        params = {**k.params, **ex.overrides}
        if params:
            md.append("\nParameters: " + ", ".join(f"`{a} = {b}`" for a, b in params.items()))
        md.append(
            f"\n**Expected result: {format_value(k, ex.expected, decimals=2)}.** {ex.working}\n"
        )
        md.append(
            "This example is asserted in `tests/test_formulas.py` against the Python function"
            + (" and in `tests/test_sql.py` against the SQL below." if k.sql else ".")
            + "\n"
        )
    md.append("## Implementations\n")
    md.append(
        '=== "Python (engine)"\n\n```python\n'
        + inspect.getsource(REGISTRY[k.id]).replace("\n", "\n")
        + "```\n"
    )
    md.append(f"Power BI measure (DAX):\n\n```dax\n[{k.name}] =\n{k.dax_expression}\n```\n")
    if k.sql:
        md.append(f"Reference SQL (tested on SQLite):\n\n```sql\n{k.sql_query}\n```\n")
    return "\n".join(md).replace(
        '=== "Python (engine)"\n\n',
        "Python function (the single implementation used by the site):\n\n",
    )


def _has_tabulate() -> bool:
    return importlib.util.find_spec("tabulate") is not None


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("–" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(lines)


def write(engine: Engine, current: dict[str, float], out_dir: Path, cases: set[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    examples = _hand_examples()
    (out_dir / "index.md").write_text(index_page(engine, current), encoding="utf-8")
    for k in engine.catalog:
        (out_dir / f"{k.id}.md").write_text(
            kpi_page(engine, k, current.get(k.id), examples, cases), encoding="utf-8"
        )
