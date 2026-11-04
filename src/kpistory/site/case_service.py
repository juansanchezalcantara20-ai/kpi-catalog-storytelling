"""Caso 1 - Atención de solicitudes (NYC 311 real, o mesa de ayuda simulada como plan B)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..engine import Engine
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
    seguimiento,
    tiles,
)
from .current import fecha, headline, mes, trimestre

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
        "# Caso 1 · Atención de solicitudes: ¿cumplimos el plazo prometido?\n",
        aviso_datos(manifest, ["tickets"]),
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
    md.append("## El contexto\n\n" + ctx)
    md.append(
        "## La pregunta del negocio\n\n"
        + pregunta(
            "¿Estamos resolviendo las solicitudes dentro del plazo que prometimos y, si no, dónde y desde cuándo falla?"
        )
    )
    md.append("## Los indicadores\n\n")
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
    md.append(
        "El cumplimiento del plazo es el resultado que siente el cliente, pero llega tarde: se mide cuando la "
        f"solicitud se cierra. Las **pendientes con más de {age_limit} días** avisan antes: lo que hoy es antiguo será un "
        "incumplimiento mañana. "
        + ("Algunos indicadores aparecen «Sin dato» porque la fuente pública no registra la primera respuesta, "
           "los contactos ni las reaperturas.\n\n" if real else "La tasa de reapertura es el contrapeso: evita que la rapidez se compre con calidad.\n\n")
    )  # fmt: skip

    # ------------------------------------------------------------------- hallazgo
    md.append("## Lo que encontramos\n\n")
    when = f"desde {mes(first_below)}" if first_below is not None else "en ningún mes"
    fig = charts.line(
        [mes(m) for m in monthly["resolved_month"]], monthly["value"],
        conclusion=f"El cumplimiento del plazo está por debajo de la meta {when}" if first_below is not None
        else "El cumplimiento del plazo se mantiene en meta todos los meses",
        subtitle="De cada 100 solicitudes cerradas en el mes, cuántas se cerraron dentro de su plazo (el eje empieza en 50 %)",
        name="Dentro del plazo", pct=True,
    )  # fmt: skip
    charts.add_target(fig, target, f"Meta {pct(target)}", pct=True)
    if first_below is not None:
        y0 = float(monthly.loc[monthly["resolved_month"].eq(first_below), "value"].iloc[0]) * 100
        charts.annotate(fig, mes(first_below), y0, "primer mes bajo la meta", ay=40)
    fig.update_yaxes(range=[50, 101])
    md.append(
        charts.to_html(
            fig,
            table=pd.DataFrame(
                {
                    "Mes": [mes(m) for m in monthly["resolved_month"]],
                    "Dentro del plazo": [pct(v, 1) for v in monthly["value"]],
                }
            ),
        )
    )

    fig = charts.bar(
        by_queue["queue"], by_queue["value"],
        conclusion=(f"El problema se concentra en «{worst['queue']}»: {pct(worst['value'])}; los demás equipos van de "
                    f"{pct(others['value'].min())} a {pct(others['value'].max())}") if len(others) else f"«{worst['queue']}»: {pct(worst['value'])}",
        subtitle=f"Solicitudes cerradas dentro del plazo, por equipo, {trimestre(q)}",
        highlight={worst["queue"]}, pct=True, text=[pct(x, 1) for x in by_queue["value"]],
    )  # fmt: skip
    charts.add_target(fig, target, f"Meta {pct(target)}", axis="x", pct=True)
    fig.update_xaxes(range=[0, 112])
    md.append(charts.to_html(fig, height=340))

    fig = go.Figure()
    for i, label in enumerate([b[2] for b in AGE_BUCKETS]):
        counts = (
            open_.groupby(["queue", "tramo"], observed=False)
            .size()
            .unstack("tramo")
            .reindex(open_by_queue.sort_values("abiertas", ascending=False).index)
        )
        fig.add_trace(go.Bar(y=counts.index, x=counts[label], name=label, orientation="h", marker_color=theme.ORDINAL[i],
                             hovertemplate=f"%{{y}} · {label}: %{{x}} solicitudes<extra></extra>"))  # fmt: skip
    fig.update_layout(barmode="stack", title=theme.title(
        f"Quedan {n(n_open)} solicitudes abiertas; {n(n_old)} llevan más de {age_limit} días, sobre todo en «{top_open}»",
        f"Solicitudes abiertas al {fecha(snapshot)}, por equipo y por antigüedad: son los próximos incumplimientos"))  # fmt: skip
    fig.update_yaxes(autorange="reversed")
    md.append(charts.to_html(fig, height=360, table=open_by_queue.reset_index().rename(
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
    md.append("## Qué decidimos\n\n")
    md.append(decisiones([
        (accion, "Jefe de la mesa de atención", fecha(review)),
        (f"Limpiar primero las {n(n_old)} solicitudes con más de {age_limit} días, empezando por «{top_open}», con una "
         "revisión diaria de las más antiguas.", "Coordinador de cada equipo", fecha(snapshot + pd.Timedelta(days=14))),
        ("No premiar solo la rapidez: cada meta de tiempo va junto a la tasa de reapertura." if not real else
         "Empezar a registrar la primera respuesta y las reaperturas: sin ellas no se puede saber si la rapidez se paga con calidad.",
         "Responsable de calidad del servicio", fecha(review)),
    ]))  # fmt: skip
    md.append("## Cómo lo seguimos midiendo\n\n")
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
