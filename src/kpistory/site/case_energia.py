"""Energía: generación eléctrica de Sudamérica (Our World in Data). Resultado observado: Chile y el carbón."""

from __future__ import annotations

import pandas as pd

from ..engine import Engine, format_value
from ..viz import charts, theme
from .common import aviso_datos, pct
from .current import headline
from .plantilla import pagina, resultado_estimado, resultado_observado, tipo_resultado

CASO = "energia"


def _share(df: pd.DataFrame, col: str) -> pd.Series:
    g = df.groupby("year")[[col, "generation_twh"]].sum()
    return g[col] / g["generation_twh"]


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    H = headline(t, e, manifest)
    en = t["energia_anual"]
    cnt = en.groupby("year")["country"].nunique()
    y = int(cnt[cnt >= cnt.max() - 1].index.max())  # last year with (almost) every country
    ev = int(e.catalog.cases[CASO]["evento"]["fecha"][:4])
    ch, pe = en[en["country"].eq("Chile")], en[en["country"].eq("Perú")]
    coal_ch, coal_pe, coal_sa = (
        _share(ch, "coal_twh"),
        _share(pe, "coal_twh"),
        _share(en, "coal_twh"),
    )
    fos = e.catalog["fossil_share_elec"]
    ci = e.catalog["carbon_intensity_elec"]
    before, after = ev - 1, int(ch["year"].max())
    c0, c1 = coal_ch.get(before), coal_ch.get(after)
    f_ch0 = e.compute("fossil_share_elec", ch[ch["year"].eq(before)])
    f_ch1 = e.compute("fossil_share_elec", ch[ch["year"].eq(after)])
    i_ch0 = e.compute("carbon_intensity_elec", ch[ch["year"].eq(before)])
    i_ch1 = e.compute("carbon_intensity_elec", ch[ch["year"].eq(after)])
    f_pe0 = e.compute("fossil_share_elec", pe[pe["year"].eq(before)])
    f_pe1 = e.compute("fossil_share_elec", pe[pe["year"].eq(int(pe["year"].max()))])
    last_y = en[en["year"].eq(y)]
    by_c = e.compute_by("carbon_intensity_elec", last_y, "country").sort_values(
        "value", ascending=False
    )
    sa_f = e.compute("fossil_share_elec", last_y)

    # --- charts
    years = list(coal_ch.index)
    g1 = charts.line(
        years, coal_ch.tolist(), pct=True, name="Chile",
        context={"Perú": (list(coal_pe.index), coal_pe.tolist()), "Sudamérica (10 países)": (list(coal_sa.index), coal_sa.tolist())},
        conclusion=f"En Chile el carbón pasó de {pct(c0)} de la electricidad en {before} a {pct(c1)} en {after}",
        subtitle="Parte de la electricidad generada con carbón, por año",
    )  # fmt: skip
    charts.annotate(g1, ev, coal_ch.get(ev) * 100, f"{ev}: plan de retiro del carbón", ay=-50)
    groups = {
        c: (list(d["year"]), (d["fossil_twh"] / d["generation_twh"]).tolist())
        for c, d in en.groupby("country")
        if len(d) > 5
    }
    g2 = charts.small_multiples(
        fos, groups, highlight={"Chile", "Perú"},
        conclusion=f"La electricidad de Sudamérica depende {pct(sa_f)} de combustibles fósiles ({y}), pero cada país es muy distinto",
        subtitle="Electricidad de combustibles fósiles por país y año; línea punteada = meta",
    )  # fmt: skip
    colors = [theme.STATUS[e.status("carbon_intensity_elec", v)] for v in by_c["value"]]
    g3 = charts.bar(
        by_c["country"], by_c["value"], colors=colors, suffix=" g", decimals=0,
        text=[format_value(ci, v, 0) for v in by_c["value"]],
        conclusion=f"«{by_c.iloc[0]['country']}» emite más por cada kilovatio hora: {format_value(ci, by_c.iloc[0]['value'], 0)} en {y}",
        subtitle="Gramos de CO₂ por kilovatio hora generado, por país; color = semáforo frente a la meta de 250 g",
    )  # fmt: skip
    analisis = (
        f"**El carbón de Chile.** Chile llegó a generar más de un tercio de su electricidad con carbón. Perú casi no usa carbón: "
        f"su parte fósil es gas natural.\n\n{charts.to_html(g1, height=420)}\n"
        f"**Cada país tiene su propia matriz.** Con la misma escala se ve quién depende más de combustibles fósiles y cuándo cambió.\n\n"
        f"{charts.to_html(g2, height=560)}\n"
        f"**Emisiones por unidad de electricidad.** Un país con mucha generación hidráulica emite poco; uno con carbón, mucho.\n\n"
        f"{charts.to_html(g3, height=420)}"
    )
    tipo = tipo_resultado(CASO, manifest)
    cuerpo = (
        f"- **Antes ({before}):** carbón {pct(c0)} de la electricidad de Chile; combustibles fósiles {format_value(fos, f_ch0)}; "
        f"emisiones {format_value(ci, i_ch0, 0)}.\n"
        f"- **Después ({after}):** carbón {pct(c1)}; combustibles fósiles {format_value(fos, f_ch1)}; emisiones {format_value(ci, i_ch1, 0)}.\n"
        f"- **Lectura:** la caída del carbón coincide con el plan de retiro anunciado en {ev} y con el crecimiento de la generación solar y eólica. "
        f"En Perú, sin un evento documentado comparable, la parte fósil pasó de {format_value(fos, f_pe0)} a {format_value(fos, f_pe1)} y no se le atribuye ninguna causa."
    )
    if tipo == "observado":
        resultado = resultado_observado(CASO, cuerpo)
    else:
        resultado = resultado_estimado(
            cuerpo.replace("coincide con el plan", "en esta simulación sigue la forma del plan"),
            "La descarga de los datos reales falló esta vez: estas cifras son simuladas y no se presentan como resultado observado.",
        )
    return pagina(
        CASO, e, H, manifest,
        titulo="Generación eléctrica: ¿qué tan expuestos estamos a los combustibles fósiles?",
        aviso=aviso_datos(manifest, ["energia"]),
        en30=(
            f"En Chile el carbón bajó de {pct(c0)} a {pct(c1)} de la electricidad entre {before} y {after}. En Perú la parte fósil (gas) es "
            f"{format_value(fos, H['fossil_share_elec'].value)} ({H['fossil_share_elec'].period}).",
            "Una matriz con mucho combustible fósil ata el costo de la electricidad al precio internacional del combustible y emite más.",
            "Retirar por etapas las centrales más contaminantes y reemplazarlas con generación renovable, sin descuidar el respaldo.",
        ),
        problema=(
            "Una empresa de generación, o un país, que produce gran parte de su electricidad con carbón o gas depende del precio de ese "
            "combustible y emite más CO₂ por cada kilovatio hora. Este caso compara los países de Sudamérica, como grupos, con datos públicos "
            "anuales de generación."
        ),
        pregunta_negocio="¿Qué parte de la electricidad depende de combustibles fósiles, y qué pasó donde se decidió reducirla?",
        analisis=analisis,
        solucion=(
            "1. **Retiro por etapas** de las centrales más antiguas y contaminantes, con fechas públicas (lo que Chile anunció en 2019).\n"
            "2. **Contratos de largo plazo con generación renovable** para reemplazar esa energía.\n"
            "3. **Seguimiento anual** de la parte fósil y de las emisiones por kilovatio hora, junto a la disponibilidad de las centrales de respaldo."
        ),
        resultado=resultado,
        tecnico=(
            f"- Tabla `energia_anual`: una fila por país y año, con `generation_twh`, `renewables_twh`, `fossil_twh`, `coal_twh` y `carbon_intensity`.\n"
            f"- Indicadores: `fossil_share_elec` = suma de `fossil_twh` / suma de `generation_twh`; `carbon_intensity_elec` ponderado por generación.\n"
            f"- El año de referencia del grupo ({y}) es el último con casi todos los países; Venezuela no tiene datos recientes en la fuente.\n"
            f"- La participación del carbón (`coal_twh` / `generation_twh`) es un dato de análisis, no un indicador del catálogo."
        ),
    )  # fmt: skip
