"""Catálogo de indicadores: un índice y una ficha por indicador, generados desde catalog.yaml."""

from __future__ import annotations

import importlib.util
import inspect
import math
import sys
from pathlib import Path

import pandas as pd

from ..catalog import KPI
from ..engine import Engine, format_threshold, format_value
from ..formulas import REGISTRY
from ..paths import TESTS_DIR
from ..viz import theme
from .common import detalle_tecnico, leyenda
from .current import Headline

MEJOR = {
    "higher_is_better": "Más alto es mejor",
    "lower_is_better": "Más bajo es mejor",
    "target_range": "Dentro de una franja",
}
UNIDAD = {
    "percent": "porcentaje",
    "hours": "horas",
    "days": "días",
    "times_per_year": "veces al año",
    "score": "puntos (de −100 a +100)",
    "g_per_kwh": "gramos de CO₂ por kilovatio hora",
    "per_million": "por millón de habitantes",
    "per_100": "por cada 100 habitantes",
    "ratio": "alumnos por docente",
}


def CASO_DE(engine: Engine, case: str) -> tuple[str, str]:
    return engine.catalog.cases[case]["title"], case


def _hand_examples() -> dict:
    path = TESTS_DIR / "hand_examples.py"
    if not path.exists():
        return {}
    spec = importlib.util.spec_from_file_location("hand_examples", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["hand_examples"] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module.BY_ID


def _value(engine: Engine, k: KPI, h: Headline | None) -> str:
    if h is None or math.isnan(h.value):
        return "⚪ Sin dato" + (f" ({h.note})" if h and h.note else "")
    status = engine.status(k.id, h.value)
    return f"{theme.STATUS_ICON[status]} {theme.STATUS_TEXT[status]} · {format_value(k, h.value)}"


def index_page(engine: Engine, values: dict[str, Headline]) -> str:
    md = [
        "# Catálogo de indicadores\n",
        f"Los **{len(engine.catalog)} indicadores** del proyecto, definidos una sola vez. Cada ficha dice qué pregunta responde, "
        "cómo se calcula en palabras, un ejemplo con números, qué decisión ayuda a tomar y con qué otro indicador se "
        "equilibra. Al final de cada ficha hay un detalle técnico desplegable con la fórmula y el código.\n",
        leyenda(),
    ]
    from ..catalog import rubros_config

    temas = rubros_config()["temas"]
    for tema, td in temas.items():
        md.append(f"\n## {td['nombre']}\n")
        md.append(f"[Ver el tema](../temas/{tema}.md)\n")
        md.append("| Indicador | Qué responde | Mejor si | Meta | Responsable | Valor actual |")
        md.append("|---|---|---|---|---|---|")
        for k in engine.catalog.for_tema(tema):
            md.append(
                f"| [{k.name}]({k.id}.md) | {k.question} | {MEJOR[k.direction]} | "
                f"{format_threshold(k, with_alert=False)} | {k.owner} | {_value(engine, k, values.get(k.id))} |"
            )
    md.append(
        "\n*Valor actual* = el mismo valor que muestran el caso y el tablero, con su periodo indicado en cada ficha. Las metas son ilustrativas.\n"
    )
    return "\n".join(md)


def kpi_page(engine: Engine, k: KPI, h: Headline | None, examples: dict) -> str:
    from ..catalog import rubros_config

    cfg = rubros_config()
    title, slug = CASO_DE(engine, k.case)
    md = [f"# {k.name}\n", f'<p class="story-question">{k.question}</p>\n', leyenda()]
    md.append(
        "**Tema:** "
        + f"[{cfg['temas'][k.tema]['nombre']}](../temas/{k.tema}.md)"
        + " · **Rubros:** "
        + ", ".join(f"[{cfg['rubros'][r]['nombre']}](../rubros/{r}.md)" for r in k.rubros)
        + "\n"
    )
    md.append(
        f"**Valor actual:** {_value(engine, k, h)}"
        + (f" · {h.period}" if h and not h.note else "")
        + f". [Ver el caso «{title}»]({'../cases/' + slug + '.md'}).\n"
    )
    md.append(
        f"**Meta:** {format_threshold(k)}. {MEJOR[k.direction]}. **Responsable:** {k.owner}.\n"
    )
    if k.metas_por_rubro:
        sign = {"higher_is_better": "≥", "lower_is_better": "≤"}.get(k.direction, "")
        md.append("**Metas por rubro:** " + "; ".join(
            f"{cfg['rubros'][r]['nombre']} {sign} {format_value(k, m['target'])} ({m['why']})" for r, m in k.metas_por_rubro.items()) + "\n")  # fmt: skip
    md.append(f"## Qué es\n\n{k.meaning}\n")
    md.append(f"## Cómo se calcula\n\n{k.calculation}\n")
    ex = examples.get(k.id)
    if ex is not None:
        md.append(f"## Ejemplo con números\n\n{ex.working}\n")
    md.append(f"## Cómo leerlo\n\n{k.how_to_read}\n")
    md.append("## Errores comunes al leerlo\n")
    md += [f"- {m}" for m in k.misreadings]
    md.append(f"\n## Qué decisión ayuda a tomar\n\n{k.decision}\n")
    rel = ", ".join(f"[{engine.catalog[r].name}]({r}.md)" for r in k.related)
    md.append(f"## Con qué se equilibra\n\n{k.balance} Indicadores relacionados: {rel}.\n")
    md.append(f"## Cómo mostrarlo\n\n{k.chart['why']}\n")

    tech = [
        f"- Identificador: `{k.id}` (tema `{k.tema}`, rubros {', '.join(f'`{r}`' for r in k.rubros)}). Unidad: {UNIDAD[k.unit]}. Detalle: {k.granularity}",
        f"- Definición formal: {k.definition}",
        f"- Fórmula: `{k.formula}`",
        f"- Tabla `{k.input['table']}`; columnas: "
        + (", ".join(f"`{c}`" for c in k.input["columns"]) or "según las reglas de calidad"),
        "- Parámetros: " + (", ".join(f"`{p} = {v}`" for p, v in k.params.items()) or "ninguno"),
        f"- Fuente: {k.source}.",
    ]
    if ex is not None:
        table = ex.table.copy()
        for col in table.columns:
            if pd.api.types.is_datetime64_any_dtype(table[col]):
                table[col] = (
                    table[col].dt.strftime("%Y-%m-%d %H:%M").str.replace(" 00:00", "", regex=False)
                )
        params = {**k.params, **ex.overrides}
        tech += [
            "",
            "Tabla del ejemplo (la misma que usa la prueba automática):",
            "",
            _md_table(table),
            "",
        ]
        if params:
            tech.append(
                "Parámetros del ejemplo: " + ", ".join(f"`{a} = {b}`" for a, b in params.items())
            )
        tech.append(f"Resultado esperado: **{format_value(k, ex.expected, decimals=2)}**, comprobado por la prueba de fórmulas"
                    + (" y por la consulta SQL." if k.sql else "."))  # fmt: skip
    tech += [
        "",
        "Función de Python (la única implementación que usa el sitio):",
        "",
        "```python",
        inspect.getsource(REGISTRY[k.id]).rstrip(),
        "```",
    ]
    if k.sql:
        tech += ["", "SQL de referencia (probado en SQLite):", "", "```sql", k.sql_query, "```"]
    md.append(detalle_tecnico("\n".join(tech)))
    return "\n".join(md)


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("–" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(lines)


def write(engine: Engine, values: dict[str, Headline], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    examples = _hand_examples()
    (out_dir / "index.md").write_text(index_page(engine, values), encoding="utf-8")
    for k in engine.catalog:
        (out_dir / f"{k.id}.md").write_text(
            kpi_page(engine, k, values.get(k.id), examples), encoding="utf-8"
        )
