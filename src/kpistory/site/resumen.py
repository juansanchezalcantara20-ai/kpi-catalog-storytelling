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


def resumen_page(vals, manifest: dict) -> str:
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
    md.append("## Todas las áreas\n")
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


def home_page(vals, manifest: dict) -> str:
    t = total_anio(vals)
    real = manifest["tickets"]["origin"] == "real"
    md = [
        "# Indicadores que se entienden\n",
        "**Un indicador no depende de la herramienta.** Cada indicador de este sitio se define una sola vez, se calcula una "
        "sola vez y se presenta de dos formas: como una **historia** que explica qué pasó y qué decidir, y como un **tablero** "
        "para revisarlo cada semana.\n",
        _total_card(vals),
        "## Para qué sirve esto\n",
        '<div class="grid cards" markdown>\n',
        "- **Un número, una verdad.** El tablero y el sitio no pueden contradecirse: los dos leen el mismo cálculo y una prueba "
        "automática falla si una cifra no coincide entre el caso, el catálogo, el tablero y este resumen.",
        "- **Del dato a la decisión.** Cada caso termina en una acción con responsable y fecha, y muestra qué se esperaba y cuánto "
        "valió con un escenario antes y después.",
        f"- **El valor en soles.** Cada brecha se traduce a soles y horas: hoy hay {money(t)} al año en juego repartidos en "
        f"{len(vals)} áreas, con supuestos que usted puede cambiar.",
        "\n</div>\n",
        "[Resumen para gerencia](resumen.md){ .md-button .md-button--primary } [Abrir el tablero](dashboard/index.html){ .md-button }\n",
        "## Qué hay adentro\n",
        "- **[Cinco casos](cases/service.md):** atención de solicitudes, mantenimiento, inventario, clientes y calidad de los datos.",
        "- **[Errores comunes al medir](antipatterns.md):** el mismo dato mostrado de una forma que engaña y de una forma honesta.",
        "- **[Catálogo de indicadores](catalog/index.md):** qué mide cada indicador, cómo se calcula, un ejemplo con números y qué decisión ayuda a tomar.",
        "- **[Cómo leer este sitio](como-leer.md):** qué es un indicador, qué es una meta y un glosario. Pase el mouse sobre las siglas subrayadas para ver su significado.\n",
        "## De dónde salen los datos\n",
        ("El caso de atención de solicitudes usa **solicitudes ciudadanas reales de Nueva York** (servicio 311). " if real else
         "El caso de atención de solicitudes usa datos simulados en esta versión porque la descarga pública no estuvo disponible. ")
        + "Los casos de mantenimiento, inventario y clientes usan datos públicos del repositorio UCI combinados con simulaciones "
        "para lo que esas fuentes no registran. Cada página dice qué parte es real y qué parte es simulada; el detalle está en "
        "[Fuentes de datos](data-sources.md).\n",
    ]  # fmt: skip
    return "\n".join(md)
