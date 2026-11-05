"""Salud: vacunación y mortalidad semanal en Sudamérica (Our World in Data). Resultado observado: Perú, 2021."""

from __future__ import annotations

import pandas as pd

from ..engine import Engine, format_value
from ..viz import charts
from .common import aviso_datos, pct
from .current import fecha, headline, mes
from .plantilla import pagina, resultado_estimado, resultado_observado, tipo_resultado

CASO = "salud"
PAIS = "Perú"


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    H = headline(t, e, manifest)
    s = t["salud_semanal"].copy()
    s["week"] = pd.to_datetime(s["week"])
    pe = s[s["country"].eq(PAIS)].sort_values("week")
    kd, kv = e.catalog["deaths_per_million_week"], e.catalog["vaccination_complete_share"]
    ev = pd.Timestamp(e.catalog.cases[CASO]["evento"]["fecha"])
    cov = pe["fully_vaccinated"] / pe["population"]
    dpm = pe["deaths"] / pe["population"] * 1e6
    pre = pe[(pe["week"] <= ev) & (pe["week"] > ev - pd.Timedelta(weeks=13))]
    reach = pe.loc[cov >= 0.5, "week"]
    post_start = reach.min() if len(reach) else pe["week"].max() - pd.Timedelta(weeks=13)
    post = pe[(pe["week"] >= post_start) & (pe["week"] < post_start + pd.Timedelta(weeks=13))]
    d_pre, d_post = (
        e.compute("deaths_per_million_week", pre),
        e.compute("deaths_per_million_week", post),
    )
    peak_i = dpm.idxmax()
    peak_w, peak_v = pe.loc[peak_i, "week"], dpm.loc[peak_i]
    whole = e.compute_by("deaths_per_million_week", s, "country").sort_values(
        "value", ascending=False
    )
    worst = whole.iloc[0]

    labels = [fecha(w) for w in pe["week"]]
    g1 = charts.kpi_trend(
        kd, labels, dpm.tolist(),
        conclusion=f"En {PAIS} la mortalidad semanal llegó a {format_value(kd, peak_v, 0)} ({mes(peak_w)}) y bajó a {format_value(kd, d_post)} cuando la mitad de la población completó su vacunación",
        subtitle="Muertes confirmadas por semana por millón de habitantes; verde = zona en meta, amarillo = margen de alerta",
        events=[(fecha(pe.loc[pe["week"] >= ev, "week"].min()), "inicio de la vacunación")],
    )  # fmt: skip
    ctx = {
        c: ([fecha(w) for w in d["week"]], (d["fully_vaccinated"] / d["population"]).tolist())
        for c, d in s.groupby("country")
        if c != PAIS
    }
    g2 = charts.line(
        labels, cov.tolist(), pct=True, name=PAIS, context=ctx,
        conclusion=f"{PAIS} pasó de 0 % a {pct(cov.iloc[-1])} de su población con vacunación completa",
        subtitle=f"Población con esquema completo; {PAIS} en azul, el resto de Sudamérica en gris",
    )  # fmt: skip
    charts.add_target(g2, kv.target, "meta", pct=True)
    g3 = charts.bar(
        whole["country"], whole["value"], highlight={PAIS}, decimals=1, suffix="",
        text=[format_value(kd, v) for v in whole["value"]],
        conclusion=f"«{worst['country']}» tuvo la mortalidad promedio más alta del grupo: {format_value(kd, worst['value'])} por semana",
        subtitle="Promedio de muertes semanales por millón de habitantes, mar 2020 a dic 2022, por país",
    )  # fmt: skip
    analisis = (
        f"**La serie semanal.** La anotación marca la semana en que empezó la vacunación.\n\n{charts.to_html(g1, height=440)}\n"
        f"**El avance de la vacunación.** Es un dato acumulado: lo que importa es su ritmo.\n\n{charts.to_html(g2, height=420)}\n"
        f"**Comparación entre países.** Siempre por millón de habitantes, nunca en números absolutos.\n\n{charts.to_html(g3, height=440)}"
    )
    cuerpo = (
        f"- **Antes:** en las 13 semanas previas al inicio de la vacunación, {format_value(kd, d_pre)} por semana; cobertura completa 0 %.\n"
        f"- **Después:** en las 13 semanas desde que la cobertura completa pasó el 50 % ({fecha(post_start)}), {format_value(kd, d_post)} por semana.\n"
        f"- **Lectura:** la caída coincide con el avance de la vacunación. También influyeron las variantes del virus, la inmunidad "
        "por contagios previos y las medidas de prevención; estos datos no separan cada efecto."
    )
    if tipo_resultado(CASO, manifest) == "observado":
        resultado = resultado_observado(CASO, cuerpo)
    else:
        resultado = resultado_estimado(
            cuerpo,
            "La descarga de los datos reales falló esta vez: estas cifras son simuladas y no se presentan como resultado observado.",
        )
    return pagina(
        CASO, e, H, manifest,
        titulo="Vacunación y mortalidad: ¿la cobertura llegó a tiempo?",
        aviso=aviso_datos(manifest, ["salud"]),
        en30=(
            f"En {PAIS} la mortalidad semanal llegó a {format_value(kd, peak_v, 0)} en {mes(peak_w)}; cuando la mitad de la población completó su "
            f"vacunación, el promedio fue {format_value(kd, d_post)}.",
            "En salud el resultado que importa no es cuántas atenciones se dieron, sino cuántas personas se protegieron.",
            "Medir la cobertura (adelantado) junto a la mortalidad (resultado) cada semana y mover vacunadores a donde se avanza más lento.",
        ),
        problema=(
            f"Entre 2020 y 2022 los países de Sudamérica enfrentaron la misma enfermedad con resultados muy distintos. {PAIS} tuvo una de las "
            "mortalidades por millón de habitantes más altas. Este caso compara países como grupos, con datos públicos semanales."
        ),
        pregunta_negocio="¿Cuánto bajó la mortalidad cuando la vacunación avanzó, y qué indicador avisa antes?",
        analisis=analisis,
        solucion=(
            "1. **Medir la cobertura completa cada semana**, por zona y grupo de edad: es el indicador adelantado.\n"
            "2. **Mover vacunadores, horarios y puntos de atención** a donde la cobertura avanza más lento.\n"
            "3. **Activar camas y personal** cuando la mortalidad semanal cruza el margen de alerta."
        ),
        resultado=resultado,
        tecnico=(
            "- Tabla `salud_semanal`: una fila por país y semana (domingos), con `population`, `fully_vaccinated` y `deaths`.\n"
            "- `deaths` = muertes semanales por millón × población / 1 000 000; la población se deduce de las personas vacunadas y su porcentaje.\n"
            "- La cobertura se arrastra día a día hasta el domingo y nunca baja (dato acumulado).\n"
            "- Ventanas del resultado: 13 semanas antes del inicio y 13 semanas desde que la cobertura pasó el 50 %."
        ),
    )  # fmt: skip
