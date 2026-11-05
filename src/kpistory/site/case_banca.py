"""Banca: morosidad de una cartera de créditos simulada, por tipo de entidad, segmento y región."""

from __future__ import annotations

import pandas as pd

from ..engine import Engine, format_value, number
from ..viz import charts, theme
from .common import aviso_datos, pct
from .current import headline, mes
from .plantilla import pagina, resultado_estimado

CASO = "banca"
SEG = "Pequeña empresa"


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    H = headline(t, e, manifest)
    c = t["creditos"].copy()
    c["month"] = pd.to_datetime(c["month"])
    k = e.catalog["npl_ratio"]
    months = sorted(c["month"].unique())
    last = months[-1]
    trend = e.compute_by("npl_ratio", c, "month")
    seg = {
        s: (list(map(mes, g["month"])), g["value"].tolist())
        for s, g in e.compute_by("npl_ratio", c, ["segment", "month"]).groupby("segment")
    }
    cl = c[c["month"].eq(last)]
    ent = e.compute_by("npl_ratio", cl, "entity_type").sort_values("value", ascending=False)
    s_all = e.compute_by("npl_ratio", c, ["segment", "month"])
    sm = s_all[s_all["segment"].eq(SEG)].set_index("month")["value"]
    base = float(sm.iloc[:9].mean())
    start = next((m for m in sm.index if sm[m] > base * 1.1), months[9])
    s_now = float(sm.iloc[-1])

    g1 = charts.kpi_trend(
        k, [mes(m) for m in trend["month"]], trend["value"].tolist(),
        conclusion=f"La morosidad total subió de {pct(trend['value'].iloc[0], 1)} a {pct(trend['value'].iloc[-1], 1)} en dos años",
        subtitle="Morosidad de toda la cartera, por mes; verde = zona en meta, amarillo = margen de alerta",
        events=[(mes(start), f"{SEG.lower()} empieza a subir")],
    )  # fmt: skip
    g2 = charts.small_multiples(
        k, seg, highlight={SEG}, cols=2,
        conclusion=f"El deterioro está en «{SEG}»: de {pct(base, 1)} a {pct(s_now, 1)}; los otros segmentos están estables",
        subtitle="Morosidad por segmento y mes, misma escala; línea punteada = meta",
    )  # fmt: skip
    g3 = charts.bar(
        ent["entity_type"], ent["value"], pct=True,
        colors=[theme.STATUS[e.status("npl_ratio", x)] for x in ent["value"]],
        text=[pct(x, 1) for x in ent["value"]],
        conclusion=f"Por tipo de entidad, «{ent.iloc[0]['entity_type']}» tiene la morosidad más alta: {pct(ent.iloc[0]['value'], 1)}",
        subtitle=f"Morosidad por tipo de entidad, {mes(last)}; color = semáforo frente a la meta de 4 %",
    )  # fmt: skip
    analisis = (
        f"**La tendencia total.** El total sube despacio y parece un problema general.\n\n{charts.to_html(g1, height=420)}\n"
        f"**Por segmento.** Con la misma escala se ve que el problema es uno solo.\n\n{charts.to_html(g2, height=460)}\n"
        f"**Por tipo de entidad.** Las entidades más expuestas a pequeña empresa tienen la morosidad más alta.\n\n{charts.to_html(g3, height=360)}"
    )
    seg_last = cl[cl["segment"].eq(SEG)]
    exceso = float(seg_last["overdue_balance"].sum() - base * seg_last["loan_balance"].sum())
    nuevo = (cl["overdue_balance"].sum() - exceso) / cl["loan_balance"].sum()
    resultado = resultado_estimado(
        f"- **Escenario:** si la morosidad de «{SEG}» volviera a su nivel de los primeros nueve meses ({pct(base, 1)}), la cartera tendría "
        f"**S/ {number(exceso / 1e6, 0)} millones menos atrasados** y la morosidad total pasaría de {pct(H['npl_ratio'].value, 1)} a {pct(nuevo, 1)}.\n"
        "- Cálculo: saldo atrasado del segmento − (morosidad base × saldo del segmento), al último mes.\n"
        f"- Contrapeso: el crecimiento de la cartera es {format_value(e.catalog['loan_growth'], H['loan_growth'].value)}; una admisión más estricta lo reduciría.\n"
        "- No es un resultado observado: toda la cartera es simulada."
    )
    return pagina(
        CASO, e, H, manifest,
        titulo="Morosidad de créditos: ¿dónde se está deteriorando la cartera?",
        aviso=aviso_datos(manifest, ["creditos"]),
        en30=(
            f"La morosidad total es {pct(H['npl_ratio'].value, 1)} ({mes(last)}), cerca de la meta de {pct(k.target)}; pero en «{SEG}» subió de "
            f"{pct(base, 1)} a {pct(s_now, 1)} desde {mes(start)}.",
            "Cada sol atrasado obliga a separar provisiones, que salen directamente de la utilidad.",
            f"Ajustar la admisión y reforzar la cobranza temprana solo en «{SEG}», sin frenar el resto de la cartera.",
        ),
        problema=(
            "Una entidad financiera mira la morosidad total cada mes. Un total que sube despacio no dice dónde está el problema ni si es general. "
            "Este caso usa una cartera **simulada** de 24 meses con cuatro tipos de entidad (banca múltiple, financieras, cajas municipales y cajas "
            "rurales), cuatro segmentos y cinco regiones: compara grupos, nunca entidades con nombre."
        ),
        pregunta_negocio="¿La morosidad sube en toda la cartera o en un segmento, y desde cuándo?",
        analisis=analisis,
        solucion=(
            f"1. **Admisión:** pedir más evidencia de ingresos en los créditos nuevos de «{SEG}».\n"
            "2. **Cobranza temprana:** llamar desde el primer día de atraso en ese segmento.\n"
            "3. **Seguimiento mensual** de la morosidad por segmento, junto al crecimiento de la cartera como contrapeso."
        ),
        resultado=resultado,
        tecnico=(
            "- Tabla `creditos`: una fila por mes, `entity_type`, `segment` y `region`, con `loan_balance` y `overdue_balance` en soles.\n"
            f"- Simulación con semilla fija: cada combinación tiene un riesgo base; desde el décimo mes la morosidad de «{SEG}» sube 2.5 % por mes.\n"
            "- Se buscó una fuente pública estable de morosidad por tipo de entidad (ver Fuentes); no se pudo verificar una descarga sin registro."
        ),
    )  # fmt: skip
