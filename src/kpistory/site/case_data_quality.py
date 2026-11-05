"""Caso 5 - Calidad de los datos como indicador."""

from __future__ import annotations

import pandas as pd

from ..data.quality import load_rules
from ..engine import Engine
from ..formulas.data_quality import timeliness_counts
from ..valor import get_valores
from ..viz import charts
from .common import (
    aviso_datos,
    bloque_bala,
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
from .current import fecha, headline
from .plantilla import ficha

DIMS = ["completeness", "uniqueness", "validity", "timeliness"]
DIM_ES = {
    "completeness": "Completitud",
    "uniqueness": "Unicidad",
    "validity": "Validez",
    "timeliness": "Oportunidad",
}


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    dq, cols, rules_df = t["dq_results"], t["dq_columns"], t["dq_rules"]
    rules = load_rules()
    H = headline(t, e, manifest)
    measured = dq[dq["total"] > 0]
    below = measured[measured["status"] != "green"]
    worst = measured.sort_values("value").iloc[0]
    trx = cols[cols["dataset"].eq("transactions")].sort_values("value")
    weakest = trx.iloc[0]
    wlabel = rules["transactions"]["labels"].get(weakest["column"], weakest["column"])
    anon_rev = 1 - t["customer_sales"]["revenue"].sum() / t["sales"]["revenue"].sum()

    md = ["# Calidad de los datos: ¿podemos confiar en los números de los otros casos?\n",
          ficha("data_quality", manifest) + aviso_datos(manifest, ["tickets", "work_orders", "process_data", "transactions", "survey"])]  # fmt: skip
    md.append(en_30_segundos(
        f"{len(below)} de {len(measured)} controles de calidad están bajo su meta. El más débil: "
        f"{DIM_ES[worst['dimension']].lower()} en «{worst['label']}» ({pct(worst['value'], 1)}).",
        f"En las ventas, el campo «{wlabel}» está vacío en {de_cada_100(1 - weakest['value'], 'líneas')}: el análisis de "
        f"clientes del caso 4 no ve {pct(anon_rev)} del ingreso.",
        "Hacer obligatorio el cliente en la venta en línea, eliminar duplicados al cargar los datos y publicar la "
        "cuadrícula de calidad con un responsable por cada casilla en rojo.",
    ))  # fmt: skip
    md.append(
        "## Problema\n\n"
        "Los casos 1 a 4 calcularon 24 indicadores sobre cinco conjuntos de datos. Cada uno supone, sin decirlo, que los "
        "datos están completos, sin duplicados, son válidos y llegaron a tiempo. Este caso mide esos supuestos con la misma "
        "disciplina que cualquier otro indicador: definición, meta, responsable y un archivo de reglas por conjunto de datos, "
        "que funciona como un pequeño **contrato de datos**. Es el puente entre el diseño de indicadores y el gobierno de "
        "datos: cada regla tiene un dueño que la corrige en el origen.\n\n"
    )
    md.append(
        "### La pregunta del negocio\n\n"
        + pregunta(
            "¿Podemos confiar en los datos de los casos 1 a 4, y qué defecto cambia un número de negocio?"
        )
    )
    md.append("## Indicadores\n\n")
    md.append(tiles(e, H, [f"dq_{d}" for d in DIMS]))
    md.append(
        "Estos valores juntan todos los conjuntos de datos, ponderados por número de filas (las ventas pesan mucho). La cuadrícula de abajo, por conjunto de datos, es la vista que importa.\n\n"
    )

    md.append(
        bloque_bala(e, H, ["dq_completeness", "dq_uniqueness", "dq_validity", "dq_timeliness"])
    )
    md.append("## Análisis\n\n")
    order = [rules[k]["label"] for k in rules]
    matrix = dq.pivot(index="label", columns="dimension", values="value")[DIMS].reindex(order)
    status = dq.pivot(index="label", columns="dimension", values="status")[DIMS].reindex(order)
    matrix.columns = status.columns = [DIM_ES[d] for d in DIMS]
    fig = charts.status_heatmap(
        matrix, status,
        conclusion=f"{len(below)} de {len(measured)} controles medibles están bajo la meta; el más débil es la "
        f"{DIM_ES[worst['dimension']].lower()} de «{worst['label']}» ({pct(worst['value'], 1)})",
        subtitle="Cuatro indicadores de calidad por conjunto de datos; el color es el semáforo frente a la meta, nunca el valor en sí",
    )  # fmt: skip
    md.append(charts.to_html(fig, height=380, table=pd.DataFrame({
        "Conjunto de datos": dq["label"], "Dimensión": dq["dimension"].map(DIM_ES), "Cumplen": dq["passed"].map(n),
        "Total": dq["total"].map(n), "Resultado": [pct(v, 1) if v == v else "no se puede medir" for v in dq["value"]]})))  # fmt: skip

    labels = [rules["transactions"]["labels"].get(c, c) for c in trx["column"]]
    fig = charts.bar(
        labels, trx["value"],
        conclusion=f"«{wlabel}» está vacío en {pct(1 - weakest['value'])} de las líneas de venta: el análisis de clientes no ve {pct(anon_rev)} del ingreso",
        subtitle="Completitud de cada campo obligatorio de las ventas, tal como llegan",
        highlight={wlabel}, pct=True, text=[pct(x, 1) for x in trx["value"]],
    )  # fmt: skip
    fig.update_xaxes(range=[0, 112])
    md.append(charts.to_html(fig, height=320))
    md.append(
        f"La completitud de todas las ventas juntas parece aceptable ({pct(matrix.loc[rules['transactions']['label'], 'Completitud'], 1)}) "
        "porque promedia seis campos: es el error de lectura que advierte el catálogo. Un solo campo carga todo el problema.\n\n"
    )

    r = rules_df[rules_df["failed_rows"] > 0].assign(share=lambda d: d["failed_rows"] / d["rows"])
    r = r.assign(
        nombre=r["dataset"].map({k: v["label"].split(" (")[0] for k, v in rules.items()})
        + ": "
        + r["rule"]
    )
    r = r.sort_values("failed_rows", ascending=False).head(8)
    top = r.iloc[0]
    fig = charts.bar(
        r["nombre"], r["failed_rows"],
        conclusion=f"La regla más incumplida es «{top['rule']}» ({n(top['failed_rows'])} filas): cada barra es un pedido de corrección al dueño del sistema de origen",
        subtitle="Filas que no cumplen cada regla de validez (solo reglas con al menos una falla)",
        highlight={top["nombre"]}, decimals=0, text=[f"{n(c)} ({pct(s, 1)})" for c, s in zip(r["failed_rows"], r["share"], strict=True)],
    )  # fmt: skip
    fig.update_xaxes(range=[0, r["failed_rows"].max() * 1.35])
    md.append(charts.to_html(fig, height=360))

    wo = t["landing_work_orders"].drop_duplicates("wo_id")
    tcfg = rules["work_orders"]["timeliness"]
    per_asset = pd.Series({a: (lambda p, q: p / q if q else float("nan"))(*timeliness_counts(g.dropna(subset=[tcfg["event_col"]]), **tcfg))
                           for a, g in wo.groupby("asset_id")}).sort_values()  # fmt: skip
    late = [a for a in per_asset.index if e.status("dq_timeliness", per_asset[a]) == "red"]
    rest = per_asset.drop(late)
    fig = charts.bar(
        per_asset.index, per_asset.values,
        conclusion=(f"{', '.join(late)} registran a tiempo solo {pct(per_asset[late].mean())} de sus órdenes de trabajo "
                    f"(las demás máquinas, al menos {pct(rest.min())}): sus indicadores de mantenimiento llegan con días de atraso")
        if late else "Todas las máquinas registran sus órdenes a tiempo",
        subtitle="Órdenes de trabajo registradas en el sistema dentro de las 24 horas siguientes a su cierre, por máquina",
        highlight=set(late), pct=True, text=[pct(x) for x in per_asset.values],
    )  # fmt: skip
    charts.add_target(
        fig,
        e.catalog["dq_timeliness"].target,
        f"Meta {pct(e.catalog['dq_timeliness'].target)}",
        axis="x",
        pct=True,
    )
    fig.update_xaxes(range=[0, 112])
    md.append(charts.to_html(fig, height=380))
    no_med = dq[dq["total"].eq(0)]["label"].tolist()
    if no_med:
        md.append(
            f"**No se puede medir:** {', '.join(no_med)} no registran la hora de carga, así que su oportunidad no se puede "
            "calcular. La cuadrícula lo dice en vez de mostrar un 100 % inventado: que falte esa columna ya es un hallazgo.\n\n"
        )
    md.append("## Solución\n\n")
    hoy = pd.Timestamp(manifest["generated_at"][:10])
    rows = [
        (
            "Hacer obligatorio el cliente en la venta en línea, o premiarlo (cuenta de cliente, compra más rápida).",
            "Jefe de ventas en línea",
            fecha(hoy + pd.Timedelta(days=60)),
        ),
        (
            "Eliminar duplicados al cargar los datos con la clave de cada conjunto.",
            "Ingeniero de datos",
            fecha(hoy + pd.Timedelta(days=30)),
        ),
    ]
    if late:
        rows.append(
            (
                f"Registro de órdenes desde el celular para las cuadrillas de {', '.join(late)}.",
                "Jefe de mantenimiento",
                fecha(hoy + pd.Timedelta(days=45)),
            )
        )
    rows += [
        (
            "Agregar la hora de carga a todas las fuentes para poder medir la oportunidad.",
            "Ingeniero de datos",
            fecha(hoy + pd.Timedelta(days=60)),
        ),
        (
            "Publicar la cuadrícula con un responsable y una fecha por cada casilla en rojo o amarillo.",
            "Responsable de los datos",
            fecha(hoy + pd.Timedelta(days=14)),
        ),
    ]
    md.append(decisiones(rows))
    v = get_valores(t, e, manifest)["data_quality"]
    md.append(seccion_valor(e, v))
    md.append(seccion_decision(e, v, rows[0][0]))
    md.append("### Cómo lo seguimos midiendo\n\n")
    md.append(seguimiento(e, [
        ("dq_completeness", "En cada carga, por campo obligatorio", "Un campo obligatorio bajo 95 %"),
        ("dq_uniqueness", "En cada carga", "Cualquier clave repetida"),
        ("dq_validity", "En cada carga, por regla", "Una regla con más de 2 % de filas que fallan"),
        ("dq_timeliness", "Cada día, por fuente", "Menos de 90 % dentro del plazo"),
    ]))  # fmt: skip
    md.append(
        "Los controles corren en el mismo proceso que calcula los indicadores de negocio: una casilla roja se ve antes de que alguien lea un número construido sobre ella.\n\n"
    )
    md.append(
        detalle_tecnico("""
- Reglas en `kpis/dq_rules.yaml`: columnas obligatorias, clave de negocio, reglas de validez (expresiones de pandas) y ventana de oportunidad.
- Se mide sobre las tablas tal como llegan (`landing_*`), antes de la limpieza.
- Completitud = celdas no vacías / celdas obligatorias (los textos en blanco cuentan como vacíos). Unicidad = claves distintas / filas. Validez = filas que cumplen todas las reglas / filas. Oportunidad = registros cargados dentro del plazo / registros.
- Los valores de las tarjetas juntan todos los conjuntos ponderados por filas; los conjuntos sin hora de carga quedan fuera de la oportunidad.
""")
    )
    return "\n".join(md)
