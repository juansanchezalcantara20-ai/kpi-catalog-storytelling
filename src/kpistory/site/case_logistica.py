"""Logística: puntualidad de salida de vuelos comerciales (Oficina de Estadísticas de Transporte de EE. UU.)."""

from __future__ import annotations

import pandas as pd

from ..engine import Engine, number
from ..viz import charts, theme
from .common import aviso_datos, pct
from .current import headline
from .plantilla import pagina, resultado_estimado

CASO = "logistica"


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    H = headline(t, e, manifest)
    v = t["vuelos"]
    k = e.catalog["on_time_share"]
    tol = k.params["tolerance_minutes"]
    total = H["on_time_share"].value
    by_h = e.compute_by("on_time_share", v, "hour_int")
    n_h = v.groupby("hour_int").size()
    by_h = by_h[by_h["hour_int"].map(n_h) >= 200]
    by_band = e.compute_by("on_time_share", v, "hour_band")
    order = [
        b
        for b in [
            "Madrugada (0 a 6 h)",
            "Mañana (6 a 10 h)",
            "Mediodía (10 a 14 h)",
            "Tarde (14 a 18 h)",
            "Noche (18 a 24 h)",
        ]
        if b in set(by_band["hour_band"])
    ]
    by_band = by_band.set_index("hour_band").loc[order].reset_index()
    best, worst = by_band.loc[by_band["value"].idxmax()], by_band.loc[by_band["value"].idxmin()]
    late = v[v["delay_minutes"] > tol]
    by_d = e.compute_by("on_time_share", v, "distance_band")

    g1 = charts.kpi_trend(
        k, [f"{h} h" for h in by_h["hour_int"]], by_h["value"].tolist(),
        conclusion=f"La puntualidad cae a lo largo del día: de {pct(by_h['value'].max())} en la mejor hora a {pct(by_h['value'].min())} en la peor",
        subtitle=f"Vuelos que salen con {tol} minutos de atraso o menos, por hora programada de salida; verde = zona en meta",
        n=[float(n_h[h]) for h in by_h["hour_int"]], n_label="vuelos",
    )  # fmt: skip
    g2 = charts.bar(
        by_band["hour_band"], by_band["value"], pct=True, horizontal=True,
        colors=[theme.STATUS[e.status("on_time_share", x)] for x in by_band["value"]],
        text=[pct(x, 1) for x in by_band["value"]],
        conclusion=f"«{worst['hour_band']}» es la franja crítica: {pct(worst['value'], 1)} a tiempo",
        subtitle="Vuelos a tiempo por franja horaria; color = semáforo frente a la meta de 80 %",
    )  # fmt: skip
    hist = (
        pd.cut(
            late["delay_minutes"],
            [tol, 30, 60, 120, 240, 10_000],
            labels=["16 a 30 min", "31 a 60 min", "1 a 2 h", "2 a 4 h", "más de 4 h"],
        )
        .value_counts()
        .sort_index()
    )
    g3 = charts.bar(
        list(hist.index.astype(str)), (hist / hist.sum()).tolist(), pct=True, horizontal=False,
        text=[pct(x, 0) for x in hist / hist.sum()],
        conclusion=f"De los vuelos atrasados, {pct(hist.iloc[:2].sum() / hist.sum())} se atrasa una hora o menos",
        subtitle=f"Cómo se reparten los {number(len(late))} vuelos atrasados según cuánto se atrasaron",
    )  # fmt: skip
    analisis = (
        f"**Hora por hora.** Los atrasos se arrastran de un vuelo al siguiente, así que se acumulan durante el día.\n\n{charts.to_html(g1, height=420)}\n"
        f"**Por franja.** Es el nivel al que se programa la operación.\n\n{charts.to_html(g2, height=360)}\n"
        f"**Cuánto se atrasan.** Por eso no conviene promediar minutos: unos pocos atrasos muy largos dispararían el promedio.\n\n{charts.to_html(g3, height=380)}"
    )
    worse = by_band[by_band["value"] < best["value"]]
    n_band = v.groupby("hour_band").size()
    gained = sum(
        (best["value"] - x) * n_band[b]
        for b, x in zip(worse["hour_band"], worse["value"], strict=True)
        if b in ("Tarde (14 a 18 h)", "Noche (18 a 24 h)")
    )
    new_total = total + gained / len(v)
    resultado = resultado_estimado(
        f"- **Escenario:** si las franjas de la tarde y la noche alcanzaran la puntualidad de «{best['hour_band']}» ({pct(best['value'], 1)}), "
        f"la puntualidad total pasaría de {pct(total, 1)} a **{pct(new_total, 1)}**: {number(gained)} vuelos más a tiempo en esta muestra.\n"
        "- Cálculo: para cada franja peor, (puntualidad de la mejor franja − puntualidad de la franja) × vuelos de la franja.\n"
        "- No es un resultado observado: la muestra no tiene fechas, así que no hay un antes y un después de ninguna decisión."
    )
    return pagina(
        CASO, e, H, manifest,
        titulo="Puntualidad en el transporte: ¿a qué hora se pierde el plazo?",
        aviso=aviso_datos(manifest, ["vuelos"]),
        en30=(
            f"{pct(total, 1)} de los vuelos sale a tiempo (meta {pct(k.target)}); en «{worst['hour_band']}» solo {pct(worst['value'], 1)}.",
            "En transporte el plazo es el producto: un atraso temprano se arrastra al resto del día y a la red.",
            "Agregar holgura y equipos de reserva en la tarde y la noche, donde se acumulan los atrasos.",
        ),
        problema=(
            "Un operador de transporte programado (pasajeros o carga) promete un horario. Si los atrasos se acumulan, el cliente pierde "
            "conexiones y el operador paga horas extra y compensaciones. Este caso usa una muestra pública de vuelos comerciales de Estados "
            "Unidos, que registra el atraso de cada salida; la lección vale para cualquier operación con rutas y horarios."
        ),
        pregunta_negocio="¿Qué parte de los viajes sale dentro de la tolerancia, y en qué horas se pierde?",
        analisis=analisis,
        solucion=(
            "1. **Holgura programada** entre viajes en la tarde y la noche, donde el atraso se arrastra.\n"
            "2. **Un equipo de reserva** disponible en las horas críticas para cortar la cadena de atrasos.\n"
            f"3. **Seguimiento semanal** de los viajes a tiempo por franja horaria, con la tolerancia de {tol} minutos."
        ),
        resultado=resultado,
        tecnico=(
            f"- Tabla `vuelos`: una fila por vuelo con `delay_minutes`, `distance_miles` y `hour` (hora programada de salida).\n"
            f"- `on_time_share` = vuelos con `delay_minutes` ≤ {tol} / vuelos. Los adelantados (atraso negativo) cuentan como a tiempo.\n"
            f"- Por distancia: " + "; ".join(f"{b}: {pct(x, 1)}" for b, x in zip(by_d["distance_band"], by_d["value"], strict=True)) + ".\n"
            "- Las horas con menos de 200 vuelos no se grafican."
        ),
    )  # fmt: skip
