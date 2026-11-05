"""Caso 1 - Atención de solicitudes (NYC 311 real, o mesa de ayuda simulada como plan B)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..engine import Engine
from ..valor import get_valores
from ..viz import charts, theme
from .common import (
    aviso_datos,
    de_cada_100,
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
from .current import fecha, headline, mes, trimestre
from .plantilla import ficha

AGE_BUCKETS = [(0, 2, "0 a 2 días"), (2, 7, "3 a 7 días"), (7, 14, "8 a 14 días"), (14, 30, "15 a 30 días"), (30, 1e9, "más de 30 días")]  # fmt: skip
PRIORITY_ORDER = ["Urgente", "Alta", "Media", "Baja"]
SLA = "plazo comprometido con el cliente (SLA)"


def _horas(h: float) -> str:
    return f"{h:.0f} h" if h < 48 else f"{h / 24:.0f} días"


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    df = t["tickets"]
    info = manifest["tickets"]
    real = info["origin"] == "real"
    H = headline(t, e, manifest)
    snapshot = pd.Timestamp(info["snapshot"])
    resolved = df[df["status"].eq("resolved")].copy()
    resolved["quarter"] = resolved["resolved_at"].dt.to_period("Q")
    q = resolved["quarter"].max()
    if resolved["resolved_at"].max() < q.end_time.normalize():
        q = q - 1
    rq = resolved[resolved["quarter"].eq(q)]
    sla = H["sla_compliance"].value
    target = e.catalog["sla_compliance"].target
    age_limit = e.catalog["backlog_aged_share"].params["age_limit_days"]

    # Monthly trend (complete months only)
    monthly = e.compute_by(
        "sla_compliance",
        resolved[
            resolved["resolved_month"]
            < (snapshot + pd.Timedelta(minutes=1)).to_period("M").start_time
        ],
        "resolved_month",
    )
    below = monthly[monthly["value"] < target]
    first_below = below["resolved_month"].min() if len(below) else None
    # By team in the reference quarter
    by_queue = e.compute_by("sla_compliance", rq, "queue").sort_values("value")
    worst = by_queue.iloc[0]
    others = by_queue.iloc[1:]
    # Open work at the cut-off
    open_ = df[df["status"].eq("open")].copy()
    open_["tramo"] = pd.cut(open_["age_days"], bins=[b[0] for b in AGE_BUCKETS] + [AGE_BUCKETS[-1][1]],
                            labels=[b[2] for b in AGE_BUCKETS], include_lowest=True)  # fmt: skip
    n_open, n_old = len(open_), int((open_["age_days"] > age_limit).sum())
    open_by_queue = open_.groupby("queue").agg(
        abiertas=("ticket_id", "size"), antiguas=("age_days", lambda s: int((s > age_limit).sum()))
    )
    top_open = open_by_queue["antiguas"].idxmax() if n_old else open_by_queue["abiertas"].idxmax()
    # The tail of the worst team
    wq = resolved[resolved["queue"].eq(worst["queue"])]
    tail = (
        wq.groupby("resolved_month")["resolution_hours"]
        .agg(tipico="median", nueve=lambda s: s.quantile(0.9))
        .reset_index()
    )
    tail = tail[
        tail["resolved_month"] < (snapshot + pd.Timedelta(minutes=1)).to_period("M").start_time
    ]
    p90_q = rq["resolution_hours"].quantile(0.9)
    # Demand of the worst team: first half of the window vs reference quarter
    weekly = df.groupby(["queue", "created_week"]).size().rename("n").reset_index()
    wq_week = weekly[weekly["queue"].eq(worst["queue"])]
    start = df["created_at"].min()
    early = wq_week[wq_week["created_week"] < start + pd.Timedelta(days=182)]["n"].mean()
    late = wq_week[wq_week["created_week"].dt.to_period("Q").eq(q)]["n"].mean()
    grew = late > early * 1.10
    if grew:
        accion = (f"Reforzar «{worst['queue']}» con personas de los equipos que están sobre la meta: su demanda subió de "
                  f"unas {early:.0f} a {late:.0f} solicitudes por semana.")  # fmt: skip
    else:
        accion = (f"Revisar cómo trabaja «{worst['queue']}»: su demanda no subió (de unas {early:.0f} a {late:.0f} "
                  "solicitudes por semana), así que el problema no es de volumen sino de proceso o de capacidad.")  # fmt: skip
    # Priorities
    deadlines = df.groupby("priority")["sla_target_hours"].first()
    prios = [p for p in PRIORITY_ORDER if p in deadlines.index]
    by_prio = e.compute_by("sla_compliance", rq, "priority").set_index("priority").reindex(prios)

    md = [
        "# Atención de solicitudes: ¿cumplimos el plazo prometido?\n",
        ficha("service", manifest) + aviso_datos(manifest, ["tickets"]),
    ]
    md.append(en_30_segundos(
        f"En {trimestre(q)}, {de_cada_100(sla, 'solicitudes')} se resolvieron dentro del {SLA}; la meta es "
        f"{round(target * 100)} de cada 100. "
        + (f"El equipo «{worst['queue']}» está por debajo: {pct(worst['value'])}." if worst["value"] < target else "Todos los equipos están en meta."),
        f"Al cierre quedan {n(n_open)} solicitudes abiertas y {n(n_old)} llevan más de {age_limit} días: "
        "cuando se cierren contarán como fuera de plazo.",
        accion + " Además, cerrar primero las pendientes más antiguas y revisar el avance en 4 semanas.",
    ))  # fmt: skip

    if real:
        ctx = (
            "Usamos las solicitudes ciudadanas al **Departamento de Transporte de Nueva York** (servicio 311) como si "
            "fueran una mesa de ayuda: cada reclamo (un semáforo dañado, un bache, una luminaria apagada) es una "
            f"solicitud con fecha de apertura, fecha de cierre, tipo y canal. Analizamos **{n(len(df))} solicitudes** "
            f"creadas entre {fecha(df['created_at'].min())} y {fecha(snapshot)}. La ciudad no publica plazos por tipo "
            "de reclamo, así que asignamos una prioridad y un plazo a cada tipo (es un supuesto nuestro, explicado en "
            "Fuentes de datos): "
        )
    else:
        ctx = (
            f"Una mesa de ayuda con cuatro equipos atendió **{n(len(df))} solicitudes** en 2024 (datos simulados). "
            "Cada solicitud tiene una prioridad con su plazo: "
        )
    ctx += ", ".join(f"**{p}** {_horas(deadlines[p])}" for p in prios) + ". "
    ctx += "Se atiende primero lo más urgente y, dentro de cada prioridad, lo más antiguo.\n\n"
    md.append("## Problema\n\n" + ctx)
    md.append(
        "### La pregunta del negocio\n\n"
        + pregunta(
            "¿Estamos resolviendo las solicitudes dentro del plazo que prometimos y, si no, dónde y desde cuándo falla?"
        )
    )
    md.append("## Indicadores\n\n")
    md.append(
        tiles(
            e,
            H,
            [
                "sla_compliance",
                "resolution_time",
                "backlog_aged_share",
                "first_response_time",
                "first_contact_resolution",
                "reopen_rate",
            ],
        )
    )
    bl = [
        kk
        for kk in ("sla_compliance", "backlog_aged_share", "resolution_time")
        if H[kk].value == H[kk].value
    ]
    fig = charts.bullets(
        [(e.catalog[kk], H[kk].value) for kk in bl],
        conclusion=f"El mayor salto hasta la meta está en las pendientes antiguas: {pct(H['backlog_aged_share'].value)} frente a "
        f"{pct(e.catalog['backlog_aged_share'].target)}" if e.status("backlog_aged_share", H["backlog_aged_share"].value) == "red"
        else "Los indicadores principales están cerca de su meta",
        subtitle="¿Cuánto falta para la meta? Barra oscura = valor actual; raya negra = meta; verde = en meta, amarillo = margen de alerta, rojo = actuar",
    )  # fmt: skip
    md.append(charts.to_html(fig, height=110 + 110 * len(bl)))
    md.append(
        "El cumplimiento del plazo es el resultado que siente el cliente, pero llega tarde: se mide cuando la "
        f"solicitud se cierra. Las **pendientes con más de {age_limit} días** avisan antes: lo que hoy es antiguo será un "
        "incumplimiento mañana. "
        + ("Algunos indicadores aparecen «Sin dato» porque la fuente pública no registra la primera respuesta, "
           "los contactos ni las reaperturas.\n\n" if real else "La tasa de reapertura es el contrapeso: evita que la rapidez se compre con calidad.\n\n")
    )  # fmt: skip

    # ------------------------------------------------------------------- hallazgo
    md.append("## Análisis\n\n")
    when = f"desde {mes(first_below)}" if first_below is not None else "en ningún mes"
    vol = resolved.groupby("resolved_month").size()
    events = [(mes(first_below), "aquí empezó")] if first_below is not None else []
    fig = charts.kpi_trend(
        e.catalog["sla_compliance"], [mes(m) for m in monthly["resolved_month"]], monthly["value"].tolist(),
        conclusion=f"El cumplimiento del plazo está por debajo de la meta {when}" if first_below is not None
        else "El cumplimiento del plazo se mantiene en meta todos los meses",
        subtitle="De cada 100 solicitudes cerradas en el mes, cuántas se cerraron dentro de su plazo; verde = zona en meta, amarillo = margen de alerta (el eje empieza en 50 %)",
        events=events, n=[float(vol.get(m, 0)) for m in monthly["resolved_month"]], n_label="solicitudes cerradas", y_range=(50, 101),
    )  # fmt: skip
    md.append(charts.to_html(fig, table=pd.DataFrame({"Mes": [mes(m) for m in monthly["resolved_month"]],
                                                     "Dentro del plazo": [pct(v, 1) for v in monthly["value"]],
                                                     "Solicitudes cerradas": [n(vol.get(m, 0)) for m in monthly["resolved_month"]]})))  # fmt: skip

    fig = charts.bar(
        by_queue["queue"], by_queue["value"],
        conclusion=(f"El problema se concentra en «{worst['queue']}»: {pct(worst['value'])}; los demás equipos van de "
                    f"{pct(others['value'].min())} a {pct(others['value'].max())}") if len(others) else f"«{worst['queue']}»: {pct(worst['value'])}",
        subtitle=f"Solicitudes cerradas dentro del plazo, por equipo, {trimestre(q)}",
        highlight={worst["queue"]}, pct=True, text=[pct(x, 1) for x in by_queue["value"]],
    )  # fmt: skip
    charts.add_target(fig, target, f"Meta {pct(target)}", axis="x", pct=True)
    fig.update_xaxes(range=[0, 112])
    qvol = rq.groupby("queue").size()
    fig.update_traces(customdata=[charts.hover_kpi(e.catalog["sla_compliance"], f"Equipo {qq}", vv, qvol.get(qq, 0), "solicitudes cerradas")
                                  for qq, vv in zip(by_queue["queue"], by_queue["value"], strict=True)],
                      hovertemplate="%{customdata}<extra></extra>")  # fmt: skip
    md.append(charts.to_html(fig, height=340))

    # ¿Qué explica el cambio? Cascada de solicitudes fuera de plazo por equipo, del mes A al mes B
    out_of_time = (
        resolved[~resolved["within_sla"].astype(bool)]
        .groupby(["resolved_month", "queue"])
        .size()
        .unstack(fill_value=0)
    )
    months_ok = [
        m
        for m in out_of_time.index
        if m < (snapshot + pd.Timedelta(minutes=1)).to_period("M").start_time
    ]
    if len(months_ok) >= 4:
        mb_, ma_ = months_ok[-1], months_ok[-4]
        steps = sorted(
            (
                (qq, int(out_of_time.loc[mb_, qq] - out_of_time.loc[ma_, qq]))
                for qq in out_of_time.columns
            ),
            key=lambda x: -abs(x[1]),
        )
        main_q = steps[0][0]
        fig = charts.waterfall(
            f"{mes(ma_)}", int(out_of_time.loc[ma_].sum()), steps, f"{mes(mb_)}",
            conclusion=f"De {n(out_of_time.loc[ma_].sum())} a {n(out_of_time.loc[mb_].sum())} solicitudes fuera de plazo al mes: "
            f"«{main_q}» explica {steps[0][1]:+d}",
            subtitle=f"Solicitudes cerradas fuera de plazo: {mes(ma_)} frente a {mes(mb_)}, y cuánto aporta cada equipo al cambio",
            unit_label="solicitudes",
        )  # fmt: skip
        md.append(charts.to_html(fig, height=380))

    # Comparar equipos: pequeños múltiples con la misma escala
    sm = e.compute_by(
        "sla_compliance",
        resolved[
            resolved["resolved_month"]
            < (snapshot + pd.Timedelta(minutes=1)).to_period("M").start_time
        ],
        ["queue", "resolved_month"],
    )
    groups = {
        qq: ([mes(m) for m in g["resolved_month"]], g["value"].tolist())
        for qq, g in sm.groupby("queue")
    }
    fig = charts.small_multiples(
        e.catalog["sla_compliance"], groups,
        conclusion=f"Solo «{worst['queue']}» se aleja de la meta; los demás equipos se mantienen cerca de ella" if len(others) and others["value"].min() >= e.catalog["sla_compliance"].thresholds["amber"]
        else f"«{worst['queue']}» es el que más se aleja de la meta",
        subtitle="Cumplimiento del plazo por mes, un panel por equipo, todos con la misma escala; la línea punteada es la meta",
        highlight={worst["queue"]},
    )  # fmt: skip
    md.append(charts.to_html(fig, height=460))

    # ¿Cómo se reparte la antigüedad? Histograma por tramos con el límite marcado
    tramos = open_["tramo"].value_counts().reindex([b[2] for b in AGE_BUCKETS]).fillna(0)
    colors = [theme.CONTEXT if i < 2 else theme.HIGHLIGHT for i in range(len(tramos))]
    fig = go.Figure(go.Bar(x=list(tramos.index), y=tramos.values, marker_color=colors, text=[n(v) for v in tramos.values],
                           textposition="outside", cliponaxis=False,
                           customdata=[f"{t_} de antigüedad · {n(v)} solicitudes abiertas · {'dentro' if i < 2 else 'fuera'} del límite de {age_limit} días"
                                       for i, (t_, v) in enumerate(tramos.items())],
                           hovertemplate="%{customdata}<extra></extra>"))  # fmt: skip
    fig.add_vline(x=1.5, line=dict(color=theme.INK, width=1.5, dash="dot"))
    fig.add_annotation(
        x=1.5,
        y=1,
        yref="paper",
        text=f"límite: {age_limit} días",
        showarrow=False,
        xanchor="left",
        yanchor="top",
        font=dict(color=theme.INK, size=11),
    )
    fig.update_layout(title=theme.title(
        f"Quedan {n(n_open)} solicitudes abiertas y {n(n_old)} ({pct(n_old / n_open if n_open else 0)}) ya pasaron el límite de {age_limit} días",
        f"Solicitudes abiertas al {fecha(snapshot)} por antigüedad; a la derecha de la línea están los próximos incumplimientos"))  # fmt: skip
    fig.update_yaxes(title_text="solicitudes abiertas")
    md.append(charts.to_html(fig, height=360))

    # ¿Dónde se concentra? Pareto de las pendientes antiguas por equipo
    aged_q = open_by_queue["antiguas"][open_by_queue["antiguas"] > 0]
    if len(aged_q):
        share_top = aged_q.max() / aged_q.sum()
        fig = charts.pareto(
            aged_q.index, aged_q.values,
            conclusion=f"«{aged_q.idxmax()}» concentra {pct(share_top)} de las pendientes antiguas: ahí está el trabajo",
            subtitle=f"Solicitudes abiertas con más de {age_limit} días por equipo, de mayor a menor, y su porcentaje acumulado",
            unit_label="pendientes antiguas",
        )  # fmt: skip
        md.append(charts.to_html(fig, height=420, table=open_by_queue.reset_index().rename(
            columns={"queue": "Equipo", "abiertas": "Abiertas", "antiguas": f"Con más de {age_limit} días"})))  # fmt: skip

    md.append(
        (
            "**¿Cómo puede el tiempo típico estar en meta y las pendientes en rojo?** "
            if e.status("resolution_time", H["resolution_time"].value) == "green" and n_old
            else "**¿Por qué se leen juntos el tiempo de resolución y las pendientes?** "
        )
        + "Miden grupos distintos. El tiempo de "
        f"resolución ({H['resolution_time'].value:.1f} h) solo mira las **{n(len(rq))} solicitudes que ya se cerraron** en "
        f"{trimestre(q)}. Las pendientes antiguas miran las **{n(n_open)} que siguen abiertas**: de ellas, **{n(n_old)} llevan "
        f"más de {age_limit} días**. Las solicitudes difíciles no aparecen en el tiempo de resolución mientras no se cierren; "
        "por eso los dos indicadores se leen juntos.\n\n"
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[mes(m) for m in tail["resolved_month"]], y=tail["tipico"], name="Solicitud típica (la del medio)",
                             mode="lines+markers", line=dict(color=theme.CONTEXT_DARK, width=2),
                             hovertemplate="%{x}: %{y:.0f} h<extra></extra>"))  # fmt: skip
    fig.add_trace(go.Scatter(x=[mes(m) for m in tail["resolved_month"]], y=tail["nueve"], name="9 de cada 10 se cierran antes de",
                             mode="lines+markers", line=dict(color=theme.HIGHLIGHT, width=2.5),
                             hovertemplate="%{x}: %{y:.0f} h<extra></extra>"))  # fmt: skip
    t_first, t_last = tail.iloc[0], tail.iloc[-1]
    fig.update_layout(showlegend=True, title=theme.title(
        f"En «{worst['queue']}», 9 de cada 10 solicitudes se cerraban en menos de {_horas(t_first['nueve'])} en "
        f"{mes(t_first['resolved_month'])} y en menos de {_horas(t_last['nueve'])} en {mes(t_last['resolved_month'])}",
        "Horas hasta el cierre, por mes: la solicitud típica y el límite bajo el que se cierran 9 de cada 10"))  # fmt: skip
    fig.update_yaxes(ticksuffix=" h")
    md.append(charts.to_html(fig, height=380))

    fig = charts.bar(
        [f"{p} ({_horas(deadlines[p])})" for p in prios], by_prio["value"].tolist(),
        conclusion=f"Por urgencia: {', '.join(f'{p} {pct(v)}' for p, v in by_prio['value'].items())}",
        subtitle=f"Solicitudes cerradas dentro del plazo según su prioridad, {trimestre(q)}",
        highlight={f"{by_prio['value'].idxmin()} ({_horas(deadlines[by_prio['value'].idxmin()])})"}, pct=True,
        text=[pct(v, 1) for v in by_prio["value"]], horizontal=False,
    )  # fmt: skip
    charts.add_target(fig, target, f"Meta {pct(target)}", pct=True)
    fig.update_yaxes(range=[0, 112])
    md.append(charts.to_html(fig, height=340))

    if "reopen_rate" not in info.get("unavailable_kpis", []):
        reop = e.compute_by(
            "reopen_rate",
            resolved.assign(
                grupo=resolved["queue"].where(resolved["queue"].eq(worst["queue"]), "Otros equipos")
            ),
            ["grupo", "resolved_month"],
        )
        fq, oq = reop[reop["grupo"].eq(worst["queue"])], reop[reop["grupo"].eq("Otros equipos")]
        fig = charts.line(
            [mes(m) for m in fq["resolved_month"]], fq["value"],
            conclusion=f"Con más presión, «{worst['queue']}» reabre más: {pct(fq['value'].iloc[:6].mean(), 1)} en el primer semestre "
            f"y {pct(fq['value'].iloc[-3:].mean(), 1)} en los últimos tres meses",
            subtitle="De cada 100 solicitudes cerradas, cuántas se reabrieron; los otros equipos en gris como referencia",
            name=worst["queue"], pct=True, context={"Otros equipos": ([mes(m) for m in oq["resolved_month"]], oq["value"])},
        )  # fmt: skip
        charts.add_target(
            fig,
            e.catalog["reopen_rate"].target,
            f"Meta {pct(e.catalog['reopen_rate'].target)}",
            pct=True,
        )
        md.append(charts.to_html(fig, height=340))

    md.append(
        "**La historia completa.** "
        + (
            (
                "El cumplimiento está bajo la meta desde el primer mes analizado. "
                if first_below == monthly["resolved_month"].min()
                else f"La caída empieza en {mes(first_below)}. "
            )
            if first_below is not None
            else ""
        )
        + f"El equipo «{worst['queue']}» recibía unas **{early:.0f} solicitudes por semana** al inicio del periodo y "
        f"**{late:.0f} por semana** en {trimestre(q)} ({'+' if late >= early else ''}{(late / early - 1) * 100:.0f} %). "
        + (
            "Como lo urgente se atiende primero, la espera se acumula en las prioridades Media y Baja y en las pendientes antiguas. "
            if not real
            else f"La prioridad con peor cumplimiento es «{by_prio['value'].idxmin()}» ({pct(by_prio['value'].min())}). "
        )
        + f"En {trimestre(q)}, 9 de cada 10 solicitudes de todos los equipos se cerraron en menos de "
        f"{_horas(p90_q)}.\n\n"
    )

    review = snapshot + pd.Timedelta(days=28)
    md.append("## Solución\n\n")
    md.append(decisiones([
        (accion, "Jefe de la mesa de atención", fecha(review)),
        (f"Limpiar primero las {n(n_old)} solicitudes con más de {age_limit} días, empezando por «{top_open}», con una "
         "revisión diaria de las más antiguas.", "Coordinador de cada equipo", fecha(snapshot + pd.Timedelta(days=14))),
        ("No premiar solo la rapidez: cada meta de tiempo va junto a la tasa de reapertura." if not real else
         "Empezar a registrar la primera respuesta y las reaperturas: sin ellas no se puede saber si la rapidez se paga con calidad.",
         "Responsable de calidad del servicio", fecha(review)),
    ]))  # fmt: skip
    v = get_valores(t, e, manifest)["service"]
    md.append(seccion_valor(e, v))
    md.append(seccion_decision(e, v, accion))
    md.append("### Cómo lo seguimos midiendo\n\n")
    md.append(seguimiento(e, [
        ("backlog_aged_share", "Cada semana, por equipo (avisa antes)", "Más de 20 % en un equipo dos semanas seguidas"),
        ("sla_compliance", "Cada mes, por equipo y prioridad", "Menos de 85 % en un equipo"),
        ("resolution_time", "Cada semana, con el «9 de cada 10»", "El «9 de cada 10» supera el plazo de la prioridad"),
        ("reopen_rate", "Cada semana, por equipo", "Más de 8 %: revisar los cierres"),
    ]))  # fmt: skip

    tech = [
        f"- Fuente: {info['name']}. {info['note']}.",
        f"- Fecha de corte (foto de las abiertas): {info['snapshot']}. Una solicitud cerrada después del corte se cuenta como abierta.",
        "- Tabla `tickets`; columnas usadas: `created_at`, `resolved_at`, `priority`, `queue`, `channel`, "
        "`sla_target_hours`, `status`, `age_days`, `resolution_hours`, `within_sla`.",
        "- Cumplimiento: `count(resolution_hours <= sla_target_hours) / count(status = resolved)`, por trimestre de cierre.",
        f"- Pendientes antiguas: `count(status = open AND age_days > {age_limit}) / count(status = open)` a la fecha de corte.",
        "- «9 de cada 10» = percentil 90 de `resolution_hours`.",
    ]
    if real:
        tech.append(
            "- Prioridad y plazo por tipo de reclamo: supuesto propio en `config/fuentes.yaml`, no una regla oficial de la ciudad."
        )
        tech.append(
            "- No incluye solicitudes creadas antes del periodo que seguían abiertas: las pendientes reales pueden ser más."
        )
    md.append(detalle_tecnico("\n".join(tech)))
    return "\n".join(md)
