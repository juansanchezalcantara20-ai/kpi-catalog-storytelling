"""Caso 2 - Mantenimiento de equipos."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..data.maintenance import FAILURE_LABEL, N_MACHINES, RUN_HOURS
from ..engine import Engine
from ..valor import get_valores
from ..viz import charts, theme
from .common import (
    aviso_datos,
    bloque_bala,
    decisiones,
    detalle_tecnico,
    en_30_segundos,
    n,
    pct,
    pregunta,
    seccion_decision,
    seccion_valor,
    seguimiento,
    tiles,
)
from .current import fecha, headline, mes

TOOL_CHANGE_AT = 190  # minutes of tool wear: proposed condition-based tool change
LONG_REPAIR_H = 12


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    runs, wo, ap = t["runs"], t["work_orders"], t["asset_periods"]
    corr = wo[wo["wo_type"].eq("corrective")]
    H = headline(t, e, manifest)
    a_target = e.catalog["availability"].target
    amber = e.catalog["availability"].thresholds["amber"]
    by_asset = pd.DataFrame(
        {
            "availability": e.compute_by("availability", ap, "asset_id").set_index("asset_id")["value"],
            "mtbf": e.compute_by("mtbf", ap, "asset_id").set_index("asset_id")["value"],
            "mttr": e.compute_by("mttr", corr, "asset_id").set_index("asset_id")["value"],
            "pm_compliance": e.compute_by("pm_compliance", wo[wo["wo_type"].eq("preventive")], "asset_id").set_index("asset_id")["value"],
            "failures": ap.groupby("asset_id")["failures"].sum(),
            "downtime_h": ap.groupby("asset_id")["unplanned_downtime_hours"].sum(),
        }
    )  # fmt: skip
    av = by_asset.sort_values("availability")
    worst = list(av.index[av["availability"] < amber]) or list(av.index[:1])
    worst_down = by_asset.loc[worst, "downtime_h"].sum() / by_asset["downtime_h"].sum()
    names = ", ".join(worst)
    med_mtbf, med_mttr = by_asset["mtbf"].median(), by_asset["mttr"].median()
    gap_mtbf, gap_mttr = by_asset["mtbf"] / med_mtbf, by_asset["mttr"] / med_mttr
    falla_mucho = [m for m in worst if 1 / gap_mtbf[m] >= gap_mttr[m]]
    repara_lento = [m for m in worst if m not in falla_mucho]
    modes = corr["failure_label"].value_counts()
    top_mode = modes.index[0]
    tool_share = corr["failure_mode"].isin(["TWF", "OSF"]).mean()
    wear = runs.assign(tramo=(runs["Tool wear [min]"] // 25 * 25).clip(upper=225))
    rate = wear.groupby("tramo")["failure_mode"].apply(lambda s: s.notna().mean())
    hi, lo = wear[wear["Tool wear [min]"] >= 200], wear[wear["Tool wear [min]"] < 200]
    ratio = hi["failure_mode"].notna().mean() / lo["failure_mode"].notna().mean()
    avoid = runs[
        runs["failure_mode"].isin(["TWF", "OSF"]) & (runs["Tool wear [min]"] >= TOOL_CHANGE_AT)
    ]
    avoid_h = (
        len(avoid) * corr.loc[corr["failure_mode"].isin(["TWF", "OSF"]), "repair_hours"].median()
    )
    mean_r, med_r = corr["repair_hours"].mean(), corr["repair_hours"].median()
    long_n = int((corr["repair_hours"] > LONG_REPAIR_H).sum())
    long_share = (
        corr.loc[corr["repair_hours"] > LONG_REPAIR_H, "repair_hours"].sum()
        / corr["repair_hours"].sum()
    )
    pm = by_asset["pm_compliance"].sort_values()
    pm_red = [m for m in pm.index if e.status("pm_compliance", pm[m]) == "red"]
    end = pd.Timestamp(ap["month"].max()) + pd.offsets.MonthEnd(0)

    md = ["# Caso 2 · Mantenimiento: ¿por qué las máquinas no están disponibles cuando se necesitan?\n",
          aviso_datos(manifest, ["process_data", "work_orders"])]  # fmt: skip
    md.append(en_30_segundos(
        f"La flota estuvo disponible {pct(H['availability'].value, 1)} del tiempo programado (meta {pct(a_target)}). "
        f"{len(worst)} de {N_MACHINES} máquinas ({names}) explican {pct(worst_down)} de las horas perdidas por fallas.",
        f"Una herramienta con más de 200 minutos de uso hace {ratio:.1f} veces más probable una falla: es una causa "
        "que se puede planificar en vez de sufrir.",
        f"Cambiar la herramienta a los {TOOL_CHANGE_AT} minutos de uso, analizar la causa en las máquinas que fallan "
        "más y tener repuestos críticos en almacén.",
    ))  # fmt: skip
    md.append(
        "## El contexto\n\n"
        f"Una planta opera **{N_MACHINES} máquinas** en dos turnos. Cada registro de los datos de proceso es una corrida "
        f"de producción de {RUN_HOURS:.0f} horas con la temperatura, la velocidad, el torque, el desgaste de la "
        f"herramienta y si hubo falla ({n(len(runs))} corridas). Cada falla abre una orden de reparación y cada máquina "
        "tiene un mantenimiento preventivo semanal.\n\n"
    )
    md.append("## La pregunta del negocio\n\n" + pregunta(
        "¿Por qué la disponibilidad está bajo la meta: porque las máquinas fallan mucho o porque tardamos en repararlas?"))  # fmt: skip
    md.append("## Los indicadores\n\n")
    md.append(tiles(e, H, ["availability", "mtbf", "mttr", "pm_compliance", "planned_work_share"]))
    md.append(
        "La disponibilidad es el resultado. Depende de dos cosas: **cada cuánto falla** una máquina (tiempo entre "
        "fallas) y **cuánto tarda en volver** (tiempo de reparación). El cumplimiento del preventivo y el trabajo "
        "planificado avisan antes: se mueven semanas antes que las fallas.\n\n"
    )

    md.append(bloque_bala(e, H, ["availability", "mtbf", "mttr", "pm_compliance"]))
    md.append("## Lo que encontramos\n\n")
    ka = e.catalog["availability"]
    av_m = e.compute_by("availability", ap, "month")
    below_m = av_m[av_m["value"] < a_target]
    first_m = below_m["month"].min() if len(below_m) else None
    worst_m = av_m.loc[av_m["value"].idxmin()]
    fig = charts.kpi_trend(
        ka, [mes(m) for m in av_m["month"]], av_m["value"].tolist(),
        conclusion=f"La flota está bajo la meta casi todo el año; el peor mes fue {mes(worst_m['month'])} con {pct(worst_m['value'], 1)}"
        if len(below_m) > len(av_m) / 2 else f"La disponibilidad cae bajo la meta en {len(below_m)} de {len(av_m)} meses",
        subtitle="Disponibilidad de toda la flota por mes; verde = zona en meta, amarillo = margen de alerta (el eje empieza en 80 %)",
        events=[(mes(worst_m["month"]), "peor mes")] + ([(mes(first_m), "aquí empezó")] if first_m is not None and first_m != worst_m["month"] else []),
        n=ap.groupby("month")["failures"].sum().reindex(av_m["month"]).tolist(), n_label="fallas", y_range=(80, 100.5),
    )  # fmt: skip
    md.append(charts.to_html(fig, height=380))
    sm = e.compute_by("availability", ap, ["asset_id", "month"])
    groups = {
        a_: ([mes(m) for m in g["month"]], g["value"].tolist()) for a_, g in sm.groupby("asset_id")
    }
    fig = charts.small_multiples(
        ka, groups, cols=5,
        conclusion=f"Las caídas no son de toda la flota: se concentran en {', '.join(worst)}",
        subtitle="Disponibilidad por mes, un panel por máquina, todos con la misma escala; la línea punteada es la meta",
        highlight=set(worst),
    )  # fmt: skip
    md.append(charts.to_html(fig, height=440))
    fig = charts.bar(
        av.index, av["availability"],
        conclusion=f"{len(worst)} de {N_MACHINES} máquinas están bajo {pct(amber)} y concentran {pct(worst_down)} de las horas perdidas",
        subtitle=f"Disponibilidad por máquina (el eje empieza en 75 %); meta {pct(a_target)}",
        highlight=set(worst), pct=True, text=[pct(x, 1) for x in av["availability"]],
    )  # fmt: skip
    charts.add_target(fig, a_target, f"Meta {pct(a_target)}", axis="x", pct=True)
    fig.update_xaxes(range=[75, 100])
    md.append(charts.to_html(fig, height=420, table=pd.DataFrame({
        "Máquina": by_asset.index, "Disponibilidad": [pct(v, 1) for v in by_asset["availability"]],
        "Horas entre fallas": [f"{v:.0f} h" for v in by_asset["mtbf"]], "Horas de reparación": [f"{v:.1f} h" for v in by_asset["mttr"]],
        "Fallas": by_asset["failures"].astype(int), "Horas perdidas": [f"{v:.0f} h" for v in by_asset["downtime_h"]]})))  # fmt: skip
    md.append(
        "*Este gráfico de barras no empieza en cero a propósito: todas las máquinas están entre 75 % y 100 % y la decisión es sobre la distancia a la meta. Lo dice el subtítulo.*\n\n"
    )

    parts = []
    if falla_mucho:
        parts.append(f"{', '.join(falla_mucho)} fallan mucho más seguido")
    if repara_lento:
        parts.append(f"{', '.join(repara_lento)} tardan más en repararse")
    diag = "; ".join(parts) + (
        ": son dos problemas distintos" if falla_mucho and repara_lento else ""
    )
    fig = go.Figure(go.Scatter(
        x=by_asset["mtbf"], y=by_asset["mttr"], mode="markers+text", text=by_asset.index, textposition="top center",
        marker=dict(size=13, color=[theme.HIGHLIGHT if m in worst else theme.CONTEXT_DARK for m in by_asset.index],
                    line=dict(color=theme.SURFACE, width=2)), textfont=dict(color=theme.INK_2),
        hovertemplate="%{text}<br>entre fallas %{x:.0f} h<br>reparación %{y:.1f} h<extra></extra>"))  # fmt: skip
    fig.add_vline(x=med_mtbf, line=dict(color=theme.AXIS, width=1))
    fig.add_hline(y=med_mttr, line=dict(color=theme.AXIS, width=1))
    fig.add_annotation(x=by_asset["mtbf"].min(), y=by_asset["mttr"].max(), text="falla seguido y tarda en repararse",
                       showarrow=False, xanchor="left", yanchor="top", font=dict(color=theme.MUTED, size=11))  # fmt: skip
    fig.add_annotation(x=by_asset["mtbf"].max(), y=by_asset["mttr"].min(), text="confiable y rápida de reparar",
                       showarrow=False, xanchor="right", yanchor="bottom", font=dict(color=theme.MUTED, size=11))  # fmt: skip
    fig.update_layout(title=theme.title(diag[0].upper() + diag[1:],
        "Cada punto es una máquina: horas entre fallas (más a la derecha es mejor) y horas de reparación (más abajo es mejor); las líneas son la mediana de la flota"))  # fmt: skip
    fig.update_xaxes(
        title_text="horas de operación entre fallas", showgrid=True, gridcolor=theme.GRID
    )
    fig.update_yaxes(title_text="horas por reparación", rangemode="normal")
    md.append(charts.to_html(fig, height=420))

    fig = charts.bar(
        modes.index, modes.values,
        conclusion=f"«{top_mode}» es la falla más frecuente ({pct(modes.iloc[0] / modes.sum())}); las fallas ligadas a la herramienta suman otro {pct(tool_share)}",
        subtitle="Órdenes de reparación por tipo de falla",
        highlight={top_mode, FAILURE_LABEL["TWF"], FAILURE_LABEL["OSF"]}, decimals=0, suffix="", text=[n(v) for v in modes.values],
    )  # fmt: skip
    md.append(charts.to_html(fig, height=320))

    labels = [f"{int(b)} a {int(b) + 24}" if b < 225 else "225 o más" for b in rate.index]
    fig = charts.bar(
        labels, rate.values,
        conclusion=f"Con más de 200 minutos de uso de la herramienta, una corrida tiene {ratio:.1f} veces más probabilidad de terminar en falla",
        subtitle="De cada 100 corridas, cuántas terminaron en falla, según los minutos de uso de la herramienta al empezar",
        highlight={lab for lab, b in zip(labels, rate.index, strict=True) if b >= 200}, pct=True, horizontal=False,
        text=[pct(x, 1) for x in rate.values],
    )  # fmt: skip
    fig.update_xaxes(title_text="minutos de uso de la herramienta")
    md.append(charts.to_html(fig, height=360))

    fig = go.Figure(go.Histogram(x=corr["repair_hours"], xbins=dict(start=0, size=1), marker_color=theme.CONTEXT,
                                 hovertemplate="%{x} h: %{y} reparaciones<extra></extra>"))  # fmt: skip
    fig.add_vline(
        x=med_r,
        line=dict(color=theme.INK_2, width=2),
        annotation=dict(text=f"típica {med_r:.1f} h", font=dict(color=theme.INK_2)),
        annotation_position="top left",
    )
    fig.add_vline(
        x=mean_r,
        line=dict(color=theme.HIGHLIGHT, width=2),
        annotation=dict(text=f"promedio {mean_r:.1f} h", font=dict(color=theme.HIGHLIGHT)),
        annotation_position="top right",
    )
    fig.add_annotation(x=corr["repair_hours"].quantile(0.97), y=3, text=f"{long_n} reparaciones de más de {LONG_REPAIR_H} h (esperando repuestos)",
                       showarrow=True, arrowhead=0, ax=0, ay=-60, font=dict(color=theme.INK))  # fmt: skip
    fig.update_layout(title=theme.title(
        f"La reparación promedio dura {mean_r:.1f} h pero la típica {med_r:.1f} h: {long_n} esperas de repuestos suman {pct(long_share)} de las horas de reparación",
        "Órdenes de reparación según su duración (barras de 1 hora)"))  # fmt: skip
    fig.update_xaxes(title_text="horas de reparación")
    fig.update_yaxes(title_text="reparaciones")
    md.append(charts.to_html(fig, height=380))

    rest = pm.drop(pm_red)
    fig = charts.bar(
        pm.index, pm.values,
        conclusion=(f"Las cuadrillas de {', '.join(pm_red)} hacen a tiempo solo {pct(pm[pm_red].mean())} de los preventivos; las demás, al menos {pct(rest.min())}")
        if pm_red else "Todas las cuadrillas hacen sus preventivos a tiempo",
        subtitle="Preventivos hechos hasta 3 días después de la fecha programada, por máquina",
        highlight=set(pm_red), pct=True, text=[pct(x) for x in pm.values],
    )  # fmt: skip
    charts.add_target(
        fig,
        e.catalog["pm_compliance"].target,
        f"Meta {pct(e.catalog['pm_compliance'].target)}",
        axis="x",
        pct=True,
    )
    fig.update_xaxes(range=[0, 110])
    md.append(charts.to_html(fig, height=400))

    wm = corr[corr["asset_id"].isin(worst)]["failure_label"].value_counts()
    md.append(
        f"**La historia completa.** La baja disponibilidad tiene dos causas: {diag.split(':')[0]}. En {names} la falla más "
        f"común es «{wm.index[0]}» ({pct(wm.iloc[0] / wm.sum())} de sus fallas). En toda la flota, el desgaste de la herramienta "
        "es la causa que más se puede controlar: el riesgo salta después de 200 minutos. El tiempo promedio de reparación se "
        "ve peor que la reparación típica por unas pocas esperas largas de repuestos. "
        + (
            f"El atraso en los preventivos se concentra en dos cuadrillas ({', '.join(pm_red)}). "
            if pm_red
            else ""
        )
        + "Las órdenes de trabajo son simuladas, así que esta página no afirma que el atraso de los preventivos cause las fallas.\n\n"
    )

    md.append("## Qué decidimos\n\n")
    rows = [(f"Cambiar la herramienta a los {TOOL_CHANGE_AT} minutos de uso. En el periodo habría convertido {len(avoid)} fallas "
             f"(unas {avoid_h:.0f} horas de parada) en cambios planificados.", "Planificador de mantenimiento", fecha(end + pd.Timedelta(days=30)))]  # fmt: skip
    if falla_mucho:
        rm = corr[corr["asset_id"].isin(falla_mucho)]["failure_label"].value_counts().index[0]
        rows.append(
            (
                f"Analizar la causa de las fallas por «{rm.lower()}» en {', '.join(falla_mucho)}: más técnicos no lo resuelven.",
                "Ingeniero de confiabilidad",
                fecha(end + pd.Timedelta(days=45)),
            )
        )
    if repara_lento:
        rows.append(
            (
                f"Revisar una por una las reparaciones largas de {', '.join(repara_lento)} (repuestos, habilidades, acceso).",
                "Supervisor de mantenimiento",
                fecha(end + pd.Timedelta(days=30)),
            )
        )
    rows.append(
        (
            f"Tener en almacén los repuestos críticos de las {long_n} reparaciones largas.",
            "Jefe de almacén",
            fecha(end + pd.Timedelta(days=60)),
        )
    )
    if pm_red:
        rows.append(
            (
                f"Reprogramar el preventivo de las cuadrillas de {', '.join(pm_red)} dentro de su turno.",
                "Planificador de mantenimiento",
                fecha(end + pd.Timedelta(days=14)),
            )
        )
    md.append(decisiones(rows))
    v = get_valores(t, e, manifest)["maintenance"]
    md.append(seccion_valor(e, v))
    md.append(seccion_decision(e, v, rows[0][0]))
    md.append("## Cómo lo seguimos midiendo\n\n")
    md.append(seguimiento(e, [
        ("pm_compliance", "Cada semana, por cuadrilla (avisa antes)", "Menos de 80 % en una cuadrilla: reprogramar la semana"),
        ("planned_work_share", "Cada mes", "Menos de 65 %: revisar las reparaciones de emergencia"),
        ("mtbf", "Cada mes por máquina, con los últimos 3 meses", "Una máquina entre las dos peores dos meses seguidos"),
        ("mttr", "Cada mes, con la reparación típica y las más largas", "Una reparación de más de 12 h: revisar repuestos"),
        ("availability", "Cada mes por máquina", "Menos de 95 %: abrir un análisis de confiabilidad"),
    ]))  # fmt: skip
    md.append(
        detalle_tecnico(f"""
- Fuente de proceso: {manifest["process_data"]["name"]} ({manifest["process_data"]["origin"]}). {manifest["process_data"]["note"]}.
- Supuesto: los {n(len(runs))} registros se reparten en {N_MACHINES} bloques seguidos = {N_MACHINES} máquinas; cada registro es una corrida de {RUN_HOURS:.0f} h, 4 por día hábil.
- Tablas `runs`, `work_orders`, `asset_periods`. Disponibilidad = `(sum(scheduled_hours) - sum(unplanned_downtime_hours)) / sum(scheduled_hours)`.
- Tiempo entre fallas = `sum(operating_hours) / sum(failures)`; tiempo de reparación = `mean(repair_hours)` de las órdenes `corrective`.
- Preventivo a tiempo: `completed_at <= due_date + 3 días`.
- Clasificación de máquinas: se compara la brecha de cada una frente a la mediana de la flota en tiempo entre fallas y en tiempo de reparación.
""")
    )
    return "\n".join(md)
