"""Telecom: líneas móviles por cada 100 habitantes en Sudamérica (ITU vía Our World in Data)."""

from __future__ import annotations

import pandas as pd

from ..engine import Engine, format_value, number
from ..viz import charts, theme
from .common import aviso_datos, pct
from .current import headline
from .plantilla import pagina, resultado_estimado

CASO = "telecom"
PAIS = "Perú"


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    H = headline(t, e, manifest)
    mo = t["moviles_anual"]
    k, kg = e.catalog["mobile_penetration"], e.catalog["lines_growth"]
    y = int(mo["year"].max())
    last = mo[mo["year"].eq(y)]
    by = e.compute_by("mobile_penetration", last, "country").sort_values("value")
    below = by[by["value"] < k.target]
    pop = last.set_index("country")["population"]
    faltan = sum(
        (k.target - v) / 100 * pop[c] for c, v in zip(below["country"], below["value"], strict=True)
    )
    sa = e.compute("mobile_penetration", last)
    years = sorted(mo["year"].unique())
    growth = [
        (yy, e.compute("lines_growth", mo[mo["year"].isin([yy - 1, yy])])) for yy in years[1:]
    ]
    slow = next((yy for yy, g in growth if g < kg.target and yy > years[5]), None)

    groups = {
        c: (list(d["year"]), (d["lines"] / d["population"] * 100).tolist())
        for c, d in mo.groupby("country")
    }
    g1 = charts.small_multiples(
        k, groups, highlight={PAIS},
        conclusion=f"En {y} el grupo tenía {format_value(k, sa)} líneas; {len(below)} de {len(by)} países seguían por debajo de 100",
        subtitle="Líneas móviles por cada 100 habitantes, por país y año; línea punteada = 100 líneas por cada 100 habitantes",
    )  # fmt: skip
    g2 = charts.bar(
        by["country"], by["value"], decimals=0,
        colors=[theme.STATUS[e.status("mobile_penetration", v)] for v in by["value"]],
        text=[format_value(k, v, 0) for v in by["value"]],
        conclusion=f"Donde queda mercado por ganar: «{by.iloc[0]['country']}» con {format_value(k, by.iloc[0]['value'], 0)}",
        subtitle=f"Líneas por cada 100 habitantes en {y}, de menor a mayor; color = semáforo frente a la meta",
    )  # fmt: skip
    g3 = charts.line(
        [yy for yy, _ in growth], [g for _, g in growth], pct=True, name="Sudamérica (10 países)",
        conclusion=f"El crecimiento de líneas del grupo cayó por debajo de {pct(kg.target)} al año desde {slow}" if slow else "El crecimiento de líneas del grupo se mantiene",
        subtitle="Crecimiento anual de las líneas móviles, suma de los 10 países",
    )  # fmt: skip
    charts.add_target(g3, kg.target, "meta", pct=True)
    analisis = (
        f"**Cuándo maduró cada mercado.** Con la misma escala se ve el año en que cada país cruzó las 100 líneas.\n\n{charts.to_html(g1, height=560)}\n"
        f"**Dónde queda espacio.** Los países por debajo de la meta todavía pueden crecer sumando personas.\n\n{charts.to_html(g2, height=420)}\n"
        f"**El indicador adelantado.** Cuando el crecimiento se acerca a cero, el negocio pasa de captar a retener.\n\n{charts.to_html(g3, height=400)}"
    )
    resultado = resultado_estimado(
        f"- **Escenario:** si los {len(below)} países por debajo de 100 llegaran a 100 líneas por cada 100 habitantes, el grupo sumaría "
        f"**{number(faltan / 1e6, 1)} millones de líneas** (cálculo: (100 − valor del país) / 100 × población del país, sumado).\n"
        f"- **En {PAIS}** ({format_value(k, H['mobile_penetration'].value, 0)}) el mercado ya está maduro: el valor está en retener y en mejores planes, no en sumar personas.\n"
        "- No es un resultado observado: la fuente no registra ninguna decisión ni un antes y un después."
    )
    return pagina(
        CASO, e, H, manifest,
        titulo="Telefonía móvil: ¿queda mercado por ganar o toca retener?",
        aviso=aviso_datos(manifest, ["moviles"]),
        en30=(
            f"En {y}, {len(below)} de {len(by)} países de Sudamérica seguían por debajo de 100 líneas por cada 100 habitantes; {PAIS} tenía "
            f"{format_value(k, H['mobile_penetration'].value, 0)}.",
            "Un mercado maduro ya no crece sumando personas: crecer exige quitar clientes a la competencia, y cuesta más.",
            "Separar la estrategia por mercado: captar donde queda espacio, retener donde ya se superaron las 100 líneas.",
        ),
        problema=(
            "Un operador de telecomunicaciones invierte en red una vez y gana cuando la llena de usuarios. Saber si un mercado todavía suma "
            "personas o ya está maduro define si conviene invertir en captar o en retener. Este caso compara países como grupos, con datos públicos anuales."
        ),
        pregunta_negocio="¿En qué mercados queda espacio para crecer y en cuáles el crecimiento ya se frenó?",
        analisis=analisis,
        solucion=(
            "1. **Mercados por debajo de 100:** cobertura y planes de entrada para sumar personas nuevas.\n"
            "2. **Mercados maduros:** retención, mejores planes y atención de reclamos (ver «Resuelto en el primer contacto»).\n"
            "3. **Seguir el crecimiento anual** de líneas como señal adelantada del cambio de etapa."
        ),
        resultado=resultado,
        tecnico=(
            "- Tabla `moviles_anual`: una fila por país y año con `population` y `lines` (= líneas por cada 100 × población / 100).\n"
            "- La fuente no trae población de 2014 a 2017: se extiende con el crecimiento de los cinco años anteriores de cada país (`estimated_population`).\n"
            f"- Datos hasta {y}, el último año publicado en la fuente."
        ),
    )  # fmt: skip
