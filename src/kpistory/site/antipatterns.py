"""Errores comunes al medir: el mismo dato mostrado mal y bien, lado a lado."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..engine import Engine
from ..viz import charts, theme
from .common import n, pct
from .current import mes

W = 34  # title wrap width for half-width charts
RAINBOW = [
    "#e6194b",
    "#3cb44b",
    "#ffe119",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#46f0f0",
    "#f032e6",
    "#bcf60c",
    "#fabebe",
]


def _pair(bad: go.Figure, good: go.Figure, height: int = 380) -> str:
    for fig in (bad, good):
        fig.update_layout(
            legend=dict(orientation="h", y=-0.18, yanchor="top", x=0, font=dict(size=10))
        )
    return (
        '<div class="pair" markdown="0">\n'
        f'<div class="bad"><p class="verdict">🔴 Engaña</p>\n{charts.to_html(bad, height=height)}</div>\n'
        f'<div class="good"><p class="verdict">🟢 Honesto</p>\n{charts.to_html(good, height=height)}</div>\n'
        "</div>\n\n"
    )


def _plain_title(text: str) -> dict:
    """The misleading charts get descriptive titles - itself one of the errors."""
    return dict(text=f"<b>{text}</b>")


def build(t: dict[str, pd.DataFrame], e: Engine) -> str:
    md = [
        "# Errores comunes al medir\n",
        "El mismo dato, mostrado de una forma que engaña (izquierda) y de una forma honesta (derecha). Todos los pares usan "
        "los datos de los casos, así que la versión honesta es la que se usa en las páginas de los casos. Las versiones que "
        "engañan no son exageraciones: son configuraciones por defecto o costumbres que se ven en informes reales.\n",
    ]

    # 1 ------------------------------------------------------------ eje que no empieza en cero
    tk = t["tickets"]
    rq = tk[
        (tk["status"] == "resolved")
        & (tk["resolved_at"] >= tk["resolved_at"].max() - pd.Timedelta(days=91))
    ]
    q = e.compute_by("sla_compliance", rq, "queue").sort_values("value")
    good_q = q.iloc[1:4] if len(q) > 3 else q
    lo = float(good_q["value"].min())
    bad = go.Figure(
        go.Bar(
            x=good_q["queue"],
            y=good_q["value"] * 100,
            marker_color=[theme.SECOND, theme.HIGHLIGHT, theme.THIRD][: len(good_q)],
        )
    )
    bad.update_layout(title=_plain_title("Cumplimiento del plazo por equipo"), showlegend=False)
    bad.update_yaxes(range=[lo * 100 - 1, 100], ticksuffix=" %")
    good = charts.bar(good_q["queue"], good_q["value"], conclusion="", subtitle="", horizontal=False, pct=True,
                      text=[pct(x, 1) for x in good_q["value"]])  # fmt: skip
    good.update_traces(
        textposition="inside", insidetextanchor="end", textfont=dict(color=theme.INK)
    )
    good.update_layout(title=theme.title(f"Los equipos están a menos de {(good_q['value'].max() - lo) * 100:.0f} puntos entre sí",
                                         "Cumplimiento del plazo, último trimestre; las barras empiezan en cero", W))  # fmt: skip
    charts.add_target(good, e.catalog["sla_compliance"].target, "Meta 90 %", pct=True)
    good.update_yaxes(range=[0, 108])
    md.append("## 1 · El eje que no empieza en cero\n")
    md.append(_pair(bad, good))
    md.append(
        f"**Por qué engaña la izquierda.** El largo de la barra representa el valor. Empezar el eje en {pct(lo - 0.01)} convierte "
        "una diferencia de pocos puntos en barras que parecen varias veces más largas, y los colores sugieren que los equipos "
        "son cosas distintas. **Qué hace la derecha:** empieza en cero, usa un solo color, dibuja la meta y su título dice qué "
        "concluir. (Las líneas sí pueden acercar el eje, porque muestran posición y no largo, pero deben decirlo.)\n"
    )

    # 2 ------------------------------------------------------------ promedio frente a mediana
    wo = t["work_orders"]
    corr = wo[wo["wo_type"].eq("corrective")]
    modes = (
        corr.groupby("failure_label")["repair_hours"]
        .agg(["mean", "median", "count"])
        .sort_values("mean", ascending=False)
    )
    modes = modes[modes["count"] >= 10]
    bad = go.Figure(go.Bar(x=modes.index, y=modes["mean"], marker_color=theme.HIGHLIGHT))
    bad.update_layout(title=_plain_title("Tiempo promedio de reparación por falla (h)"))
    good = go.Figure()
    for m in modes.index:
        good.add_trace(go.Box(y=corr.loc[corr["failure_label"].eq(m), "repair_hours"], name=m, marker_color=theme.CONTEXT_DARK,
                              line=dict(width=1.5), boxpoints="outliers", showlegend=False))  # fmt: skip
    worst = modes["mean"].idxmax()
    good.update_layout(title=theme.title(
        f"Una reparación típica dura entre {modes['median'].min():.1f} y {modes['median'].max():.1f} h; los promedios los inflan unas pocas esperas de repuestos",
        "Horas por reparación (la caja es la mitad central, la línea la reparación típica y los puntos los casos extremos)", W))  # fmt: skip
    good.update_yaxes(
        type="log",
        title_text="horas (escala logarítmica)",
        tickvals=[1, 2, 5, 10, 20, 50],
        ticktext=["1", "2", "5", "10", "20", "50"],
    )
    md.append("## 2 · El promedio que esconde la cola larga\n")
    md.append(_pair(bad, good))
    md.append(
        f"**Por qué engaña la izquierda.** Los tiempos de reparación son muy desparejos: casi todas las reparaciones son cortas "
        f"y unas pocas esperan días por repuestos. El promedio de «{worst}» ({modes.loc[worst, 'mean']:.1f} h) no describe casi "
        f"ninguna reparación real: la típica dura {modes.loc[worst, 'median']:.1f} h. Ordenar las fallas por su promedio es "
        "ordenarlas por sus casos extremos. **Qué hace la derecha:** muestra toda la distribución, así se ve la reparación "
        "típica y la cola larga, y la decisión apunta a la cola (repuestos), no a los técnicos.\n"
    )

    # 3 ------------------------------------------------------------ demasiadas series
    fc = t["forecast"]
    top = fc.groupby("sku")["actual_units"].sum().nlargest(10).index
    w = (
        fc[fc["sku"].isin(top)]
        .pivot_table(index="week", columns="sku", values="actual_units", aggfunc="sum")
        .fillna(0)
    )
    w = w[w.index >= w.index.max() - pd.Timedelta(days=364)]
    ratio = w.tail(12).mean() / w.head(12).mean().where(lambda x: x > 0)
    star = ratio.idxmin()
    stopped = w[star].tail(8).sum() == 0
    last_sale = w.index[w[star] > 0].max()
    bad = go.Figure()
    for i, s in enumerate(w.columns):
        bad.add_trace(
            go.Scatter(
                x=w.index, y=w[s], name=s, mode="lines", line=dict(color=RAINBOW[i % 10], width=1.5)
            )
        )
    bad.update_layout(
        title=_plain_title("Demanda semanal, 10 productos principales"),
        showlegend=True,
        legend=dict(font=dict(size=9)),
    )
    good = go.Figure()
    for s in w.columns:
        if s != star:
            good.add_trace(go.Scatter(x=w.index, y=w[s], mode="lines", line=dict(color=theme.CONTEXT, width=1), showlegend=False,
                                      hovertemplate=f"{s}: %{{y:.0f}}<extra></extra>"))  # fmt: skip
    good.add_trace(go.Scatter(x=w.index, y=w[star], mode="lines", line=dict(color=theme.HIGHLIGHT, width=2.5), showlegend=False,
                              hovertemplate=f"{star}: %{{y:.0f}}<extra></extra>"))  # fmt: skip
    charts.annotate(good, w[star].idxmax(), float(w[star].max()), f"producto {star}", ay=-30)
    good.update_layout(title=theme.title(
        (f"El producto {star}, uno de los 10 que más se venden, dejó de venderse después de {mes(last_sale)}: su inventario queda en riesgo"
         if stopped else f"El producto {star} perdió {(1 - ratio[star]) * 100:.0f} % de su demanda semanal en un año"),
        "Unidades por semana de los 10 productos principales; los otros nueve en gris como referencia", W))  # fmt: skip
    md.append("## 3 · Demasiadas series\n")
    md.append(_pair(bad, good))
    md.append(
        "**Por qué engaña la izquierda.** Diez colores superan lo que cualquiera puede emparejar con una leyenda, varios son "
        "iguales para personas con daltonismo y ninguna línea es más importante que otra: el gráfico no tiene mensaje. "
        "**Qué hace la derecha:** una sola serie destacada lleva el mensaje, las demás quedan en gris como contexto y la "
        "etiqueta va sobre la línea. Si todas importan, se usan gráficos pequeños separados.\n"
    )

    # 4 ------------------------------------------------------------ torta frente a barras
    counts = corr["failure_label"].value_counts()
    bad = go.Figure(
        go.Pie(
            labels=counts.index,
            values=counts.values,
            marker=dict(colors=RAINBOW),
            sort=False,
            textinfo="label",
        )
    )
    bad.update_layout(title=_plain_title("Fallas por tipo"), showlegend=False)
    good = charts.bar(counts.index, counts.values, conclusion="", subtitle="", highlight={counts.index[0]}, decimals=0,
                      text=[f"{n(c)} ({pct(c / counts.sum())})" for c in counts.values])  # fmt: skip
    good.update_layout(title=theme.title(
        f"«{counts.index[0]}» encabeza con {pct(counts.iloc[0] / counts.sum())}; «{counts.index[1].lower()}» es un segundo claro",
        "Órdenes de reparación por tipo de falla, de mayor a menor", W))  # fmt: skip
    good.update_xaxes(range=[0, counts.max() * 1.45])
    md.append("## 4 · La torta con demasiadas porciones\n")
    md.append(_pair(bad, good))
    md.append(
        f"**Por qué engaña la izquierda.** Comparamos mal ángulos y áreas: con {len(counts)} porciones, el orden de las del medio "
        "es adivinanza y las pequeñas desaparecen. **Qué hace la derecha:** barras ordenadas sobre la misma base muestran el "
        "orden y las diferencias exactas. Una torta solo sirve para dos o tres partes de un total (la barra de recomendación "
        "del caso de clientes es el único gráfico de partes de un total del sitio).\n"
    )

    # 5 ------------------------------------------------------------ semáforo sin meta
    ap = t["asset_periods"]
    av = e.compute_by("availability", ap, "asset_id").set_index("asset_id")["value"].sort_index()
    fleet = float(av.mean())
    rel = ["red" if x < fleet else "green" for x in av]
    bad = go.Figure(
        go.Scatter(
            x=list(av.index),
            y=[1] * len(av),
            mode="markers",
            marker=dict(size=20, color=[theme.STATUS[s] for s in rel]),
        )
    )
    bad.update_layout(title=_plain_title("Estado de las máquinas"))
    bad.update_yaxes(visible=False, range=[0.5, 1.5])
    bad.update_xaxes(showline=False, ticks="")
    target, amber = e.catalog["availability"].target, e.catalog["availability"].thresholds["amber"]
    order = av.sort_values().index
    status = [e.status("availability", av[m]) for m in order]
    good = go.Figure(go.Bar(y=list(order), x=av[order] * 100, orientation="h", marker_color=[theme.STATUS[s] for s in status],
                            text=[f"{theme.STATUS_ICON[s]} {pct(av[m], 1)}" for s, m in zip(status, order, strict=True)],
                            textposition="outside", cliponaxis=False))  # fmt: skip
    good.add_vrect(
        x0=amber * 100,
        x1=target * 100,
        fillcolor="rgba(250,178,25,0.12)",
        line_width=0,
        layer="below",
    )
    charts.add_target(good, target, f"Meta {pct(target)}", axis="x", pct=True)
    good.update_layout(title=theme.title(
        f"{status.count('red')} máquinas para actuar, {status.count('amber')} para vigilar, {status.count('green')} en meta",
        f"Disponibilidad frente a una meta de {pct(target)}; franja amarilla entre {pct(amber)} y {pct(target)}; el eje empieza en 75 %", W))  # fmt: skip
    good.update_xaxes(range=[75, 103], ticksuffix=" %")
    good.update_yaxes(autorange="reversed")
    md.append("## 5 · El semáforo sin meta\n")
    md.append(_pair(bad, good, height=420))
    md.append(
        f"**Por qué engaña la izquierda.** Los colores comparan cada máquina con el promedio de la flota ({pct(fleet, 1)}), así que "
        "cerca de la mitad sale en rojo *por construcción*, aunque todas cumplieran la meta; y puntos rojos y verdes no dicen "
        "valor, ni meta, ni sirven a personas con daltonismo. **Qué hace la derecha:** el semáforo sale de la meta del "
        "catálogo, el valor está escrito, la meta y la franja de alerta están dibujadas y cada color va con su texto.\n"
    )

    # 6 ------------------------------------------------------------ dos ejes
    tkm = tk.groupby("created_month").size()
    slam = e.compute_by(
        "sla_compliance", tk[tk["status"] == "resolved"], "resolved_month"
    ).set_index("resolved_month")["value"]
    bad = go.Figure()
    bad.add_trace(go.Bar(x=tkm.index, y=tkm.values, name="Solicitudes", marker_color=theme.CONTEXT))
    bad.add_trace(
        go.Scatter(
            x=slam.index,
            y=slam.values * 100,
            name="Cumplimiento",
            yaxis="y2",
            line=dict(color=theme.SECOND, width=3),
        )
    )
    bad.update_layout(title=_plain_title("Solicitudes y cumplimiento"),
                      yaxis2=dict(overlaying="y", side="right", range=[slam.min() * 100 - 0.5, slam.max() * 100 + 0.5], ticksuffix=" %", showgrid=False))  # fmt: skip
    worst_q = q.iloc[0]["queue"]
    fs = tk[tk["queue"].eq(worst_q)].groupby("created_month").size()
    others = tk[~tk["queue"].eq(worst_q)].groupby("created_month").size()
    idx_fs, idx_ot = fs / fs.iloc[:6].mean() * 100, others / others.iloc[:6].mean() * 100
    good = charts.line(idx_fs.index, idx_fs.values, conclusion="", subtitle="", name=worst_q, decimals=0,
                       context={"Otros equipos": (idx_ot.index, idx_ot.values)})  # fmt: skip
    good.update_layout(title=theme.title(
        f"La demanda de «{worst_q}» llegó a {idx_fs.iloc[-1]:.0f} respecto a sus primeros seis meses (= 100); los demás equipos siguen cerca de 100",
        "Solicitudes creadas por mes, en base 100 = promedio de los primeros seis meses (un solo eje)", W))  # fmt: skip
    good.update_yaxes(rangemode="tozero")
    md.append("## 6 · Dos ejes verticales en un mismo gráfico\n")
    md.append(_pair(bad, good))
    md.append(
        "**Por qué engaña la izquierda.** Las dos escalas son independientes: dónde se cruza la línea con las barras depende de "
        "cómo se eligieron los rangos, así que inventa una relación (o la esconde). Además, el total mezcla el equipo que "
        "cambió con los que no. **Qué hace la derecha:** un solo eje, las dos series en la misma base y la comparación que "
        "explica la caída del caso de atención de solicitudes. El cumplimiento va en su propio gráfico al lado.\n"
    )
    md.append(
        "---\n\nLas reglas detrás de las versiones honestas están en [Cómo leer este sitio](como-leer.md).\n"
    )
    return "\n".join(md)
