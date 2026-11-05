"""Home page and «Resumen para gerencia», generated from the same value numbers as the dashboard."""

from __future__ import annotations

from ..valor import money, top_alertas, total_anio, units
from .common import valor_card

SLUG = {
    "service": "service",
    "maintenance": "maintenance",
    "inventory": "inventory",
    "customers": "customers",
    "data_quality": "data_quality",
}


def _total_card(vals) -> str:
    t = total_anio(vals)
    activas = sum(1 for v in vals.values() if v.soles_mes > 0)
    return (
        f'<div class="valor-card" markdown="0" data-valor-total="{round(t)}"><div>Valor en juego</div>'
        f'<div class="grande">{money(t)} al año</div>'
        f'<div class="sub">repartidos en {len(vals)} áreas ({activas} con brecha frente a su meta) · '
        f"{money(t / 12)} al mes</div>"
        '<div class="aviso-supuestos">Supuestos ilustrativos; cámbielos con los de su empresa en el tablero o en cada caso.</div></div>\n\n'
    )


def resumen_page(vals, manifest: dict, engine=None, values=None) -> str:
    from ..engine import Engine
    from .ejes import resumen_por_rubro

    engine = engine or Engine()
    md = ["# Resumen para gerencia\n"]
    md.append(
        "Lo que una gerencia necesita en un minuto: cuánto vale cerrar las brechas de los indicadores, dónde está el dinero "
        "y qué hacer el lunes. Todas las cifras salen del mismo cálculo que el tablero y los casos.\n"
    )
    md.append(_total_card(vals))
    md.append("## Las 3 alertas más caras\n")
    for i, v in enumerate(top_alertas(vals), start=1):
        md.append(f"### {i} · {v.titulo}: {money(v.soles_mes)} al mes\n")
        md.append(valor_card(v, nota="en el simulador del tablero o del caso"))
        md.append(
            f"- **Qué pasa:** {v.resumen_brecha}.\n"
            f"- **Acción recomendada:** {v.accion}\n"
            f"- **Responsable:** {v.responsable} · **Fecha de revisión:** {v.fecha}\n"
            f"- [Ver el caso completo](cases/{SLUG[v.caso]}.md)\n"
        )
    if values is not None:
        md.append(resumen_por_rubro(engine, values, vals))
    md.append("## Todas las áreas con valor en soles\n")
    md.append("| Área | Brecha | Al mes | Al año | Horas al mes |")
    md.append("|---|---|---|---|---|")
    for v in sorted(vals.values(), key=lambda x: -x.soles_anio):
        md.append(
            f"| [{v.titulo}](cases/{SLUG[v.caso]}.md) | {v.resumen_brecha} | {money(v.soles_mes)} | {money(v.soles_anio)} | {units(v.horas_mes)} |"
        )
    md.append(
        "\n## Qué cambia en una empresa que trabaja así\n\n"
        "- **Una sola definición por indicador.** Cada número se calcula una vez, de una sola forma, y todos lo leen igual.\n"
        "- **Nadie discute el número; se discute la decisión.** La reunión pasa de «¿de dónde salió esta cifra?» a «¿qué hacemos y quién lo hace?».\n"
        "- **Las alertas llegan antes de que el cliente reclame.** Los indicadores adelantados avisan semanas antes que los resultados.\n"
        "- **Cada brecha tiene precio.** Priorizar es ordenar por soles y horas, no por quién grita más fuerte.\n"
    )
    md.append(
        "[Abrir el tablero](dashboard/index.html){ .md-button .md-button--primary } [Cómo leer este sitio](como-leer.md){ .md-button }\n"
    )
    return "\n".join(md)


def home_page(vals, manifest: dict, engine=None, values=None) -> str:
    from ..catalog import rubros_config
    from ..engine import Engine
    from .ejes import ETIQUETA, contador, destacados, matriz
    from .plantilla import con_datos_reales, tipo_resultado

    engine = engine or Engine()
    cfg = rubros_config()
    t = total_anio(vals)
    md = [
        "# Indicadores que se entienden\n",
        "**Un indicador bien definido convierte un dato en una decisión con responsable, fecha y valor en soles.** Cada indicador "
        "de este sitio se define una sola vez, se calcula una sola vez y se presenta de dos formas: como una **historia** "
        "(problema → solución → resultado) y como un **tablero** para revisarlo cada semana.\n",
        contador(engine, manifest),
        _total_card(vals),
        "## Para qué sirve esto\n",
        '<div class="grid cards" markdown>\n',
        "- **Un número, una verdad.** El tablero y el sitio no pueden contradecirse: los dos leen el mismo cálculo y una prueba "
        "automática falla si una cifra no coincide entre el caso, el catálogo, el tablero y este resumen.",
        "- **Del dato a la decisión.** Cada caso sigue la misma estructura: problema, indicadores, análisis, solución y resultado, "
        "y el resultado dice si fue observado en datos reales o estimado con un escenario.",
        f"- **El valor en soles.** Donde hay supuestos de valor, cada brecha se traduce a soles y horas: hoy hay {money(t)} al año en "
        "juego, con supuestos que usted puede cambiar.",
        "\n</div>\n",
        "[Resumen para gerencia](resumen.md){ .md-button .md-button--primary } [Abrir el tablero](dashboard/index.html){ .md-button }\n",
        f"## {len(cfg['rubros'])} rubros × {len(cfg['temas'])} temas\n",
        "Cada fila es un rubro (sector) y cada columna un tema. Un clic en una celda abre el caso o el tablero filtrado.\n",
        matriz(engine, manifest),
        "## Tres casos para empezar\n",
    ]
    for c in destacados(engine, manifest):
        d = engine.catalog.cases[c]
        rub = ", ".join(cfg["rubros"][r]["nombre"] for r in d["rubros"])
        datos = (
            "datos reales" if con_datos_reales(c, manifest) else "datos simulados o de referencia"
        )
        md.append(
            f"- **[{d['title']}](cases/{c}.md)** · {rub} · {ETIQUETA[tipo_resultado(c, manifest)]} · {datos}"
        )
    md += [
        "\n## Qué más hay adentro\n",
        "- **[Por rubro](rubros/index.md)** y **[por tema](temas/index.md):** los indicadores que mira cada sector y cada tipo de problema.",
        "- **[Catálogo de indicadores](catalog/index.md):** qué mide cada indicador, cómo se calcula, un ejemplo con números y qué decisión ayuda a tomar.",
        "- **[Cómo leer este sitio](como-leer.md):** qué es un indicador, qué es una meta, los errores comunes al medir y un glosario.",
        "- **[Fuentes](data-sources.md):** de dónde sale cada dato, con su licencia, fecha de descarga y filas.\n",
    ]
    return "\n".join(md)
