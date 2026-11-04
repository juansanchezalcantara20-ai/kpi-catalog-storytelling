"""Caso 4 - Clientes."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..engine import Engine
from ..formulas.customers import PANDAS_PERIOD, nps_margin_of_error, retention_series
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
from .current import fecha, headline, trimestre

SEGMENTS = [
    "Campeones",
    "Leales",
    "Nuevos o prometedores",
    "Requieren atención",
    "En riesgo",
    "Dormidos",
]
RISK = "En riesgo"


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    sales, cs, rfm, survey = t["sales"], t["customer_sales"], t["customer_rfm"], t["survey"]
    H = headline(t, e, manifest)
    end = sales["invoice_date"].max()
    period = e.catalog["retention_rate"].params["period"]
    ret = retention_series(cs, period)
    last_p = cs["invoice_date"].max().to_period(PANDAS_PERIOD[period])
    if cs["invoice_date"].max() < last_p.end_time.normalize():
        ret = ret.drop(index=str(last_p), errors="ignore")
    anon_rev = 1 - cs["revenue"].sum() / sales["revenue"].sum()
    nps = H["nps"].value
    moe = nps_margin_of_error(survey["score"])
    risk = rfm[rfm["segment"].eq(RISK)].sort_values("monetary", ascending=False)
    half = (
        int((risk["monetary"].cumsum() <= risk["monetary"].sum() / 2).sum()) + 1 if len(risk) else 0
    )

    md = [
        "# Caso 4 · Clientes: ¿los estamos conservando y a quién llamamos primero?\n",
        aviso_datos(manifest, ["transactions", "survey"]),
    ]
    md.append(en_30_segundos(
        f"De los clientes que compraron en un trimestre, {de_cada_100(H['retention_rate'].value, 'volvieron')} a comprar el "
        f"trimestre siguiente ({trimestre(ret.index[-1])}).",
        f"Los clientes buenos que dejaron de comprar («en riesgo») representan {pct(H['revenue_at_risk_share'].value)} del "
        f"ingreso del último año, y {half} de ellos explican la mitad de ese ingreso.",
        f"Campaña de recuperación con la lista de esos {half} clientes, ordenada por ingreso, y llamada a los clientes que "
        "nos calificaron mal en menos de 48 horas.",
    ))  # fmt: skip
    md.append(
        "## El contexto\n\n"
        f"La misma tienda del caso 3. **{n(cs['customer_id'].nunique())} clientes identificados** compraron entre "
        f"{fecha(sales['invoice_date'].min())} y {fecha(end)}. Las compras sin cliente identificado representan "
        f"{pct(anon_rev)} del ingreso y no entran aquí (se miden en el caso 5). Una encuesta de recomendación llegó a los "
        f"clientes del último año ({n(len(survey))} respuestas; la encuesta es simulada).\n\n"
    )
    md.append(
        "## La pregunta del negocio\n\n"
        + pregunta("¿Estamos conservando a nuestros clientes y a quién tenemos que llamar primero?")
    )
    md.append("## Los indicadores\n\n")
    md.append(
        tiles(e, H, ["retention_rate", "repeat_purchase_rate", "revenue_at_risk_share", "nps"])
    )
    md.append(
        "Que los clientes vuelvan es el resultado. El **ingreso en riesgo** avisa antes y, sobre todo, da una lista de "
        f"nombres. La recomendación agrega la voz del cliente, siempre con su número de respuestas (aquí ± {moe:.0f} puntos de margen de error).\n\n"
    )

    md.append("## Lo que encontramos\n\n")
    rs = pd.DataFrame({"q": list(ret.index), "v": ret.values})
    lo, hi = rs.loc[rs["v"].idxmin()], rs.loc[rs["v"].idxmax()]
    fig = charts.line(
        [trimestre(q) for q in rs["q"]], rs["v"],
        conclusion=f"Vuelven entre {pct(lo['v'])} ({trimestre(lo['q'])}) y {pct(hi['v'])} ({trimestre(hi['q'])}) de los clientes: "
        f"en promedio {de_cada_100(1 - rs['v'].mean(), 'clientes')} de un trimestre no compran en el siguiente",
        subtitle="De cada 100 clientes de un trimestre, cuántos volvieron a comprar en el siguiente (solo trimestres completos)",
        name="Volvieron a comprar", pct=True,
    )  # fmt: skip
    charts.add_target(
        fig,
        e.catalog["retention_rate"].target,
        f"Meta {pct(e.catalog['retention_rate'].target)}",
        pct=True,
    )
    fig.update_yaxes(range=[0, 100])
    md.append(
        charts.to_html(
            fig,
            height=340,
            table=pd.DataFrame(
                {
                    "Trimestre": [trimestre(q) for q in rs["q"]],
                    "Volvieron": [pct(v, 1) for v in rs["v"]],
                }
            ),
        )
    )

    seg = rfm.groupby("segment").agg(clientes=("customer_id", "count"), ingreso=("monetary", "sum"))
    seg = seg.reindex([s for s in SEGMENTS if s in seg.index])
    seg["parte"] = seg["ingreso"] / seg["ingreso"].sum()
    seg = seg.sort_values("ingreso", ascending=False)
    fig = charts.bar(
        seg.index, seg["parte"],
        conclusion=f"Los clientes «en riesgo» (compraban seguido y bastante, pero hace tiempo que no compran) dejaron "
        f"{pct(H['revenue_at_risk_share'].value)} del ingreso; {half} de ellos explican la mitad",
        subtitle="Parte del ingreso del último año según el tipo de cliente",
        highlight={RISK}, pct=True, text=[f"{pct(s)} · {c} clientes" for s, c in zip(seg["parte"], seg["clientes"], strict=True)],
    )  # fmt: skip
    fig.update_xaxes(range=[0, seg["parte"].max() * 135])
    md.append(
        charts.to_html(
            fig,
            height=340,
            table=pd.DataFrame(
                {
                    "Tipo de cliente": seg.index,
                    "Clientes": seg["clientes"].values,
                    "Parte del ingreso": [pct(v, 1) for v in seg["parte"]],
                }
            ),
        )
    )
    md.append(
        "Los tipos de cliente salen de tres preguntas: qué tan reciente fue su última compra, cada cuánto compra y "
        "cuánto compra. Son relativos a esta tienda: «en riesgo» significa «peor que los demás en recencia», no un umbral fijo.\n\n"
    )

    rows = []
    for s in SEGMENTS:
        sub = survey[survey["segment"].eq(s)]
        if len(sub) >= 10:
            rows.append(
                {
                    "seg": s,
                    "n": len(sub),
                    "nps": e.compute("nps", sub),
                    "moe": nps_margin_of_error(sub["score"]),
                }
            )
    by_seg = pd.DataFrame(rows).sort_values("nps")
    fig = go.Figure(go.Scatter(
        x=by_seg["nps"], y=by_seg["seg"], mode="markers",
        error_x=dict(type="data", array=by_seg["moe"], color=theme.CONTEXT_DARK, thickness=1.5, width=6),
        marker=dict(size=11, color=[theme.HIGHLIGHT if s == RISK else theme.CONTEXT_DARK for s in by_seg["seg"]]),
        customdata=by_seg[["n", "moe"]], hovertemplate="%{y}: %{x:+.0f} ± %{customdata[1]:.0f} (%{customdata[0]} respuestas)<extra></extra>"))  # fmt: skip
    fig.add_vline(x=0, line=dict(color=theme.INK_2, width=1))
    best, worst = by_seg.iloc[-1], by_seg.iloc[0]
    fig.update_layout(title=theme.title(
        f"La recomendación va de {best['nps']:+.0f} ({best['seg']}) a {worst['nps']:+.0f} ({worst['seg']}); las líneas muestran qué diferencias son reales",
        "Recomendación por tipo de cliente con su margen de error (solo tipos con al menos 10 respuestas)"))  # fmt: skip
    fig.update_xaxes(
        range=[-100, 100],
        title_text="recomendación (de −100 a +100)",
        showgrid=True,
        gridcolor=theme.GRID,
        zeroline=False,
    )
    md.append(charts.to_html(fig, height=360))

    det, pas, pro = (
        (survey["score"] <= 6).mean(),
        survey["score"].between(7, 8).mean(),
        (survey["score"] >= 9).mean(),
    )
    fig = go.Figure()
    for share, label, color in (
        (det, "Detractores (0 a 6)", theme.SECOND),
        (pas, "Neutros (7 y 8)", theme.CONTEXT),
        (pro, "Promotores (9 y 10)", theme.HIGHLIGHT),
    ):
        fig.add_trace(go.Bar(y=["Todas las respuestas"], x=[share * 100], name=label, orientation="h", marker_color=color,
                             text=[f"{label.split(' ')[0]} {pct(share)}"], textposition="inside", insidetextanchor="middle",
                             hovertemplate=f"{label}: {pct(share, 1)}<extra></extra>"))  # fmt: skip
    fig.update_layout(barmode="stack", showlegend=True, title=theme.title(
        f"Recomendación {nps:+.0f} = {pct(pro)} de promotores menos {pct(det)} de detractores; la nota promedio "
        f"({survey['score'].mean():.1f} sobre 10) escondería esa división",
        "Respuestas por grupo: el único gráfico de partes de un total del sitio, con exactamente tres partes"))  # fmt: skip
    fig.update_xaxes(ticksuffix=" %", range=[0, 100])
    md.append(charts.to_html(fig, height=230))
    md.append(
        "*La encuesta es simulada y sus notas se generaron según el tipo de cliente; la relación entre tipo de cliente y "
        "recomendación es un supuesto, no un hallazgo. El gráfico muestra cómo leer la recomendación: por grupo, con el número "
        "de respuestas y su margen de error.*\n\n"
    )
    md.append(
        f"**La historia completa.** Cada trimestre se va una parte importante de los compradores, y entre los que se van hay "
        f"clientes que compraban mucho: {len(risk)} clientes «en riesgo» explican {pct(H['revenue_at_risk_share'].value)} del "
        f"ingreso. Llamar a los {half} primeros recupera la mitad de esa oportunidad.\n\n"
    )
    md.append("## Qué decidimos\n\n")
    md.append(decisiones([
        (f"Campaña de recuperación con la lista de clientes «en riesgo» ordenada por ingreso: los primeros {half} explican la mitad. Llamada de un ejecutivo, no un correo masivo.", "Responsable de relación con clientes", fecha(end + pd.Timedelta(days=30))),
        ("Llamar a los clientes que nos calificaron de 0 a 6 en menos de 48 horas y registrar el motivo.", "Responsable de experiencia del cliente", fecha(end + pd.Timedelta(days=14))),
        ("Medir la recompra por año de primera compra antes de fijar una sola meta.", "Analista comercial", fecha(end + pd.Timedelta(days=45))),
        (f"Reducir las compras sin cliente identificado ({pct(anon_rev)} del ingreso): sin ese dato no hay seguimiento posible.", "Jefe de ventas en línea", fecha(end + pd.Timedelta(days=60))),
    ]))  # fmt: skip
    md.append("## Cómo lo seguimos midiendo\n\n")
    md.append(seguimiento(e, [
        ("revenue_at_risk_share", "Cada mes, con la lista de clientes (avisa antes)", "Más de 20 %: ampliar la campaña"),
        ("retention_rate", "Cada trimestre, por año de primera compra", "Menos de 40 %"),
        ("repeat_purchase_rate", "Cada mes, últimos 12 meses", "Menos de 50 %"),
        ("nps", "En cada encuesta, con su número de respuestas", "Una caída mayor que el margen de error"),
    ]))  # fmt: skip
    md.append(
        detalle_tecnico(f"""
- Ventas: {manifest["transactions"]["name"]} ({manifest["transactions"]["origin"]}). {manifest["transactions"]["note"]}.
- Solo facturas con `customer_id`. Retención trimestral: `|clientes(t-1) ∩ clientes(t)| / |clientes(t-1)|`, solo trimestres completos.
- Segmentos: recencia, frecuencia y monto en quintiles (1 a 5) sobre 12 meses, con reglas fijas en el código (`RFM_SEGMENTS`).
- Recomendación: `100 × (notas 9-10 − notas 0-6) / respuestas`; margen de error al 95 % por varianza multinomial.
- Encuesta simulada con semilla fija: las notas dependen del segmento por diseño.
""")
    )
    return "\n".join(md)
