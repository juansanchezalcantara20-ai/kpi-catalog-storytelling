"""Building blocks shared by the case pages (all reader-facing text in Spanish)."""

from __future__ import annotations

import html
import math

from ..engine import Engine, format_threshold, format_value, number
from ..engine import pct as _pct
from ..viz import theme
from .current import Headline, fecha

LEYENDA = "🟢 En meta · 🟡 Vigilar · 🔴 Actuar"
AYUDA = "Pase el mouse (o toque) una tarjeta para ver qué mide, cómo se calcula y por qué esa meta."


def pct(x: float, d: int = 0) -> str:
    return _pct(x, d)


def n(x: float) -> str:
    return number(x, 0)


def de_cada_100(x: float, cosa: str) -> str:
    """0.892, 'solicitudes' -> '89 de cada 100 solicitudes'."""
    return f"{round(x * 100):.0f} de cada 100 {cosa}"


def leyenda(ayuda: bool = True) -> str:
    extra = f" {AYUDA}" if ayuda else ""
    return f'<p class="leyenda" markdown="0">Semáforo: {LEYENDA}. El color siempre va con su texto.{extra}</p>\n\n'


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
    """One card per KPI: Spanish name, value, target, traffic light with text, what it means.

    Hovering (or focusing, or tapping) the card shows the catalog explanation; hovering the
    traffic light shows the rule behind its colour.
    """
    up = "../" * depth
    cards, tips = [], []
    for kid in ids:
        k = engine.catalog[kid]
        h = values[kid]
        status = engine.status(kid, h.value)
        value = format_value(k, h.value) if not math.isnan(h.value) else "Sin dato"
        extra = h.note or h.period
        tip_id, rule_id = f"tip-{kid}", f"regla-{kid}"
        tips += [tip_kpi(k, tip_id), tip_rule(k, status, rule_id)]
        cards.append(
            f'<a class="kpi-tile status-{status.replace("/", "")}" href="{up}catalog/{k.id}/" data-kpi="{k.id}" '
            f'data-tip aria-describedby="{tip_id}">'
            f'<span class="kpi-name">{html.escape(k.name)}</span>'
            f'<span class="kpi-value">{html.escape(value)}</span>'
            f'<span class="kpi-status" data-tip aria-describedby="{rule_id}">{theme.STATUS_ICON[status]} '
            f"{theme.STATUS_TEXT[status]} · meta {html.escape(format_threshold(k, with_alert=False))}</span>"
            f'<span class="kpi-meaning">{html.escape(k.meaning)}</span>'
            f'<span class="kpi-context">{html.escape(extra)}</span></a>'
        )
    return (
        leyenda()
        + '<div class="kpi-grid" markdown="0">\n'
        + "\n".join(cards)
        + "\n</div>\n"
        + '<div markdown="0">'
        + "".join(tips)
        + "</div>\n\n"
    )


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


# ---------------------------------------------------------------- tooltips
def status_rule(k, status: str) -> str:
    """Plain-language rule behind a traffic light, e.g. '🟡 Vigilar: fuera de meta pero dentro del margen de alerta (≤ 4.0 h)'."""
    g, a = k.thresholds["green"], k.thresholds["amber"]
    f = lambda v: format_value(k, v)  # noqa: E731
    if k.direction == "higher_is_better":
        meta, alerta = f"≥ {f(g)}", f"≥ {f(a)}"
    elif k.direction == "lower_is_better":
        meta, alerta = f"≤ {f(g)}", f"≤ {f(a)}"
    else:
        meta, alerta = f"entre {f(g[0])} y {f(g[1])}", f"entre {f(a[0])} y {f(a[1])}"
    return {
        "green": f"🟢 En meta: cumple la meta ({meta}).",
        "amber": f"🟡 Vigilar: fuera de meta pero dentro del margen de alerta ({alerta}).",
        "red": f"🔴 Actuar: fuera de la meta y del margen de alerta ({alerta}).",
        "n/a": "⚪ Sin dato: la fuente de datos no registra lo necesario para calcularlo.",
    }[status]


def tip_kpi(k, tip_id: str) -> str:
    """Hidden tooltip with the catalog explanation of a KPI (shown on hover, focus or tap)."""
    e = html.escape
    return (
        f'<div class="kpi-tip" role="tooltip" id="{tip_id}" hidden><b>{e(k.name)}</b><dl>'
        f"<dt>Qué mide</dt><dd>{e(k.meaning)}</dd>"
        f"<dt>Cómo se calcula</dt><dd>{e(k.calculation)}</dd>"
        f"<dt>Meta y por qué</dt><dd>{e(format_threshold(k))}. {e(k.target_why)}</dd>"
        f"<dt>Qué decisión ayuda a tomar</dt><dd>{e(k.decision)}</dd>"
        f"<dt>Con qué se equilibra</dt><dd>{e(k.balance)}</dd>"
        f"<dt>Responsable</dt><dd>{e(k.owner)}</dd></dl></div>"
    )


def tip_rule(k, status: str, tip_id: str) -> str:
    return f'<div class="kpi-tip" role="tooltip" id="{tip_id}" hidden>{html.escape(status_rule(k, status))}</div>'


# ---------------------------------------------------------------- value
def valor_card(v, depth: int = 2, nota: str = "en el simulador de abajo") -> str:
    """Big card: what not acting costs. data-* attributes let the tests compare pages."""
    from ..valor import money, units

    sub = (
        f"{money(v.soles_anio)} al año · {v.resumen_brecha}"
        if v.soles_mes > 0
        else v.resumen_brecha
    )
    return (
        f'<div class="valor-card" markdown="0" data-caso="{v.caso}" data-valor-mes="{round(v.soles_mes)}" data-valor-anio="{round(v.soles_anio)}">'
        f'<div class="grande">{money(v.soles_mes)} al mes · {units(v.horas_mes)} horas de trabajo</div>'
        f'<div class="sub">{html.escape(sub)}</div>'
        f'<div class="aviso-supuestos">Supuestos ilustrativos; cámbielos con los de su empresa {nota}.</div></div>\n\n'
    )


def seccion_valor(engine: Engine, v) -> str:
    """'Lo que cuesta no actuar': big card, assumptions table and the embedded '¿y si…?' simulator."""
    import json

    from ..valor import money, units

    md = ["## Lo que cuesta no actuar\n", valor_card(v)]
    rows = [
        "| Indicador | Hoy | Meta | Base | De más al mes | Supuesto | Costo al mes |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in v.componentes:
        k = engine.catalog[c.kpi]
        rows.append(
            f"| {c.nombre} | {format_value(k, c.valor)} | {format_threshold(k, with_alert=False)} | {units(c.base)} {c.base_texto} | "
            f"{units(c.unidades_de_mas)} {c.unidad} | {c.explicacion_costo} | {money(c.soles_mes)} |"
        )
    md.append("\n".join(rows) + "\n")
    md.append(
        "Cómo se calcula: unidades de más = base × distancia a la meta (nunca negativa); costo = unidades de más × costo "
        "por unidad. Si el indicador ya está en meta, el costo es cero.\n"
    )
    data = {"caso": v.caso, "componentes": [
        {k2: getattr(c, k2) for k2 in ("kpi", "nombre", "valor", "meta", "direccion", "unidad_pct", "base", "unidad", "costo_unitario", "horas_unitarias")}
        for c in v.componentes]}  # fmt: skip
    md.append(
        f'<div class="simulador" data-sim="{v.caso}" markdown="0"><script type="application/json">'
        f"{json.dumps(data, ensure_ascii=False)}</script></div>\n\n"
    )
    return "\n".join(md)


def seccion_decision(engine: Engine, v, decision: str) -> str:
    """'De la decisión al resultado': before/after line with the decision date, value captured, '¿es ruido?'."""
    from ..valor import money
    from ..viz import charts

    esc = v.escenario
    if esc is None:
        return ""
    k = engine.catalog[v.componentes[0].kpi]
    mejora = esc.mejora * (100 if k.unit == "percent" else 1)
    lo, hi = (x * (100 if k.unit == "percent" else 1) for x in esc.intervalo)
    unidad = "puntos" if k.unit == "percent" else {"hours": "h", "days": "días"}.get(k.unit, "")
    fig = charts.scenario(
        k, esc,
        conclusion=f"Con la decisión, «{k.name}» se acerca a la meta y se capturan {money(esc.valor_capturado)} en seis meses (escenario simulado)",
        subtitle=f"Últimos meses con datos y seis meses proyectados desde {esc.fecha_decision}, con y sin la decisión",
        hist_labels=esc.meses_historia,
    )  # fmt: skip
    ruido = (
        f"el intervalo de 90 % va de {lo:+.1f} a {hi:+.1f} {unidad} e incluye el cero: **todavía podría ser ruido**; hay que esperar más meses antes de celebrar."
        if esc.es_ruido
        else f"el intervalo de 90 % va de {lo:+.1f} a {hi:+.1f} {unidad} y no incluye el cero: **no es ruido**, el cambio es real dentro del escenario."
    )
    md = ["## De la decisión al resultado\n"]
    md.append(
        f"- **Qué se decidió:** {decision}\n"
        f"- **Qué se esperaba:** {esc.explicacion}\n"
        f"- **Qué pasó después (simulado de forma transparente):** el escenario proyecta seis meses con y sin la decisión, con la "
        f"misma variación mes a mes que tuvieron los datos. Comparando los últimos seis meses con los meses 4 a 6 después de la decisión, "
        f"el indicador cambia {mejora:+.1f} {unidad}; {ruido}\n"
        f"- **Cuánto valió:** {money(esc.valor_capturado)} en seis meses frente a no hacer nada.\n"
    )
    md.append(charts.to_html(fig, height=400))
    return "\n".join(md)


def bloque_bala(engine: Engine, values: dict[str, Headline], ids: list[str]) -> str:
    """'¿Cuánto falta para la meta?': bullet charts; the title names the KPI farthest from target."""
    from ..valor import gap
    from ..viz import charts

    items = [(engine.catalog[k], values[k].value) for k in ids if not math.isnan(values[k].value)]
    rel = {k.id: gap(v, k.target if k.direction != "target_range" else k.thresholds["green"][1], k.direction if k.direction != "target_range" else "lower_is_better")
           / (abs(k.target) or 1) for k, v in items}  # fmt: skip
    worst = max(rel, key=rel.get)
    kw = engine.catalog[worst]
    conclusion = (
        f"El mayor salto hasta la meta está en «{kw.name}»: {format_value(kw, values[worst].value)} frente a "
        f"{format_threshold(kw, with_alert=False)}"
        if rel[worst] > 0
        else "Todos los indicadores principales están en meta"
    )
    fig = charts.bullets(items, conclusion, "¿Cuánto falta para la meta? Barra oscura = valor actual; raya negra = meta; "
                                            "verde = en meta, amarillo = margen de alerta, rojo = actuar")  # fmt: skip
    return charts.to_html(fig, height=110 + 110 * len(items))
