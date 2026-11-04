"""Building blocks shared by the case pages (all reader-facing text in Spanish)."""

from __future__ import annotations

import html
import math

from ..engine import Engine, format_threshold, format_value, number
from ..engine import pct as _pct
from ..viz import theme
from .current import Headline, fecha

LEYENDA = "🟢 En meta · 🟡 Vigilar · 🔴 Actuar"


def pct(x: float, d: int = 0) -> str:
    return _pct(x, d)


def n(x: float) -> str:
    return number(x, 0)


def de_cada_100(x: float, cosa: str) -> str:
    """0.892, 'solicitudes' -> '89 de cada 100 solicitudes'."""
    return f"{round(x * 100):.0f} de cada 100 {cosa}"


def leyenda() -> str:
    return f'<p class="leyenda" markdown="0">Semáforo: {LEYENDA}. El color siempre va con su texto.</p>\n\n'


def en_30_segundos(que_paso: str, por_que_importa: str, que_decidimos: str) -> str:
    return (
        '!!! abstract "En 30 segundos"\n'
        f"    **Qué pasó.** {que_paso}\n\n"
        f"    **Por qué importa.** {por_que_importa}\n\n"
        f"    **Qué se decidió.** {que_decidimos}\n\n"
    )


def aviso_datos(manifest: dict, keys: list[str]) -> str:
    """Data notice: real, real + simulation, or simulated - never a silent mix."""
    items = [manifest[k] for k in keys]
    reales = [m for m in items if m["origin"] == "real"]
    simulados = [m for m in items if m["origin"] != "real"]
    if reales:
        fuentes = "; ".join(
            f"[{html.escape(m['name'])}]({m['url']}), descargados el {fecha(m['downloaded_at'])}"
            for m in reales
        )
        texto = f"**Datos reales:** {fuentes}."
        if simulados:
            texto += (
                " **Se combinan con datos simulados** para lo que la fuente pública no registra: "
                + ", ".join(
                    m["name"]
                    .replace(" (simulados)", "")
                    .replace(" (simuladas)", "")
                    .replace(" (simulada)", "")
                    .lower()
                    for m in simulados
                )
                + ". La parte simulada muestra el método; no describe una empresa real."
            )
        return f'!!! info "De dónde salen estos datos"\n    {texto} Detalle en [Fuentes de datos](../data-sources.md).\n\n'
    return (
        '!!! warning "Datos simulados"\n'
        "    **Datos simulados: muestran el método, no describen una empresa real.** "
        "Detalle y motivo en [Fuentes de datos](../data-sources.md).\n\n"
    )


def tiles(engine: Engine, values: dict[str, Headline], ids: list[str], depth: int = 2) -> str:
    """One card per KPI: Spanish name, value, target, traffic light with text, what it means."""
    up = "../" * depth
    cards = []
    for kid in ids:
        k = engine.catalog[kid]
        h = values[kid]
        status = engine.status(kid, h.value)
        value = format_value(k, h.value) if not math.isnan(h.value) else "Sin dato"
        extra = h.note or h.period
        cards.append(
            f'<a class="kpi-tile status-{status.replace("/", "")}" href="{up}catalog/{k.id}/" data-kpi="{k.id}">'
            f'<span class="kpi-name">{html.escape(k.name)}</span>'
            f'<span class="kpi-value">{html.escape(value)}</span>'
            f'<span class="kpi-status">{theme.STATUS_ICON[status]} {theme.STATUS_TEXT[status]} · '
            f"meta {html.escape(format_threshold(k, with_alert=False))}</span>"
            f'<span class="kpi-meaning">{html.escape(k.meaning)}</span>'
            f'<span class="kpi-context">{html.escape(extra)}</span></a>'
        )
    return leyenda() + '<div class="kpi-grid" markdown="0">\n' + "\n".join(cards) + "\n</div>\n\n"


def pregunta(text: str) -> str:
    return f'<p class="story-question">{html.escape(text)}</p>\n\n'


def decisiones(rows: list[tuple[str, str, str]]) -> str:
    """rows: (decisión, responsable, revisión)."""
    out = ["| Qué decidimos | Responsable | Revisión |", "|---|---|---|"]
    out += [f"| {d} | {r} | {f} |" for d, r, f in rows]
    return "\n".join(out) + "\n\n"


def seguimiento(engine: Engine, rows: list[tuple[str, str, str]]) -> str:
    """rows: (kpi_id, frecuencia, cuándo actuar). Responsable y meta salen del catálogo."""
    out = [
        "| Indicador | Responsable | Frecuencia | Meta | Cuándo actuar |",
        "|---|---|---|---|---|",
    ]
    for kid, cadence, trigger in rows:
        k = engine.catalog[kid]
        out.append(
            f"| [{k.name}](../catalog/{k.id}.md) | {k.owner} | {cadence} | "
            f"{format_threshold(k, with_alert=False)} | {trigger} |"
        )
    return "\n".join(out) + "\n\n"


def detalle_tecnico(markdown: str) -> str:
    """Collapsed block (closed by default): the only place for column names and formulas."""
    body = "\n".join("    " + line if line else "" for line in markdown.strip().splitlines())
    return f'??? tecnico "Detalle técnico"\n{body}\n\n'
