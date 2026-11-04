"""Caso 3 - Inventario y demanda."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..data.inventory import MA_WEEKS, N_FADED, N_TOP, ORDER_UP_TO_WEEKS
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
from .current import fecha, headline, mes


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    ol, daily, snap, fc = (
        t["order_lines"],
        t["inventory_daily"],
        t["inventory_snapshot"],
        t["forecast"],
    )
    H = headline(t, e, manifest)
    end = daily["date"].max()
    start12 = end - pd.Timedelta(days=364)
    ol12, d12, fc12 = (
        ol[ol["order_date"] >= start12],
        daily[daily["date"] >= start12],
        fc[fc["week"] >= start12],
    )
    periodo = f"{mes(start12)} – {mes(end)}"

    lines = ol12.assign(
        corto=ol12["qty_shipped"] < ol12["qty_ordered"],
        tarde=ol12["delivered_date"] > ol12["promised_date"],
    )
    orders = lines.groupby("order_id")[["corto", "tarde"]].any()
    cats = pd.Series({
        "Completo y a tiempo": (~orders["corto"] & ~orders["tarde"]).mean(),
        "Incompleto": (orders["corto"] & ~orders["tarde"]).mean(),
        "Tarde": (~orders["corto"] & orders["tarde"]).mean(),
        "Incompleto y tarde": (orders["corto"] & orders["tarde"]).mean(),
    })  # fmt: skip
    top_fail = cats.drop("Completo y a tiempo").idxmax()
    order_size = lines.groupby("order_id").size().mean()

    mb = e.compute_by("forecast_bias", fc.assign(m=fc["week"].dt.to_period("M").dt.start_time), "m")
    mb = mb[
        (mb["m"] >= start12 - pd.Timedelta(days=62)) & (mb["m"] + pd.offsets.MonthEnd(0) <= end)
    ]
    lo_band, hi_band = e.catalog["forecast_bias"].thresholds["green"]
    lowest, highest = mb.loc[mb["value"].idxmin()], mb.loc[mb["value"].idxmax()]
    sw = e.compute_by(
        "stockout_rate",
        d12.assign(semana=d12["date"].dt.to_period("W-SUN").dt.start_time),
        "semana",
    )
    so = d12[d12["active"] & (d12["on_hand_units"] <= 0)]
    under_months = set(mb.loc[mb["value"] < lo_band, "m"])
    under_share = (
        so["date"].dt.to_period("M").dt.start_time.isin(under_months).mean()
        if len(so)
        else float("nan")
    )
    peak = sw.loc[sw["value"].idxmax()]
    age_limit = e.catalog["obsolescence_share"].params["age_limit_days"]
    old = snap[snap["days_since_last_movement"] > age_limit]
    faded_old = int(old["sku_group"].eq("Dejó de venderse").sum())

    md = [
        "# Caso 3 · Inventario: ¿atendemos a los clientes sin inmovilizar dinero de más?\n",
        aviso_datos(manifest, ["transactions", "inventory"]),
    ]
    md.append(en_30_segundos(
        f"Se despacharon {de_cada_100(H['fill_rate'].value, 'unidades pedidas')}, pero solo "
        f"{de_cada_100(H['otif'].value, 'pedidos')} llegaron completos y a tiempo.",
        f"El pronóstico se queda corto antes de la temporada alta ({lowest['value'] * 100:+.0f} % en {mes(lowest['m'])}) y se pasa "
        f"después ({highest['value'] * 100:+.0f} % en {mes(highest['m'])}): primero faltan productos y luego sobran.",
        "Pronosticar la temporada con el año anterior, anticipar el inventario antes del pico y liquidar lo que dejó de venderse.",
    ))  # fmt: skip
    md.append(
        "## El contexto\n\n"
        "Una tienda en línea de artículos de regalo vende sobre todo a pequeños comercios; la demanda sube antes de "
        f"Navidad. El equipo de planificación pronostica cada producto con el **promedio de las últimas {MA_WEEKS} semanas**, "
        f"revisa el inventario cada lunes y pide hasta cubrir {ORDER_UP_TO_WEEKS:.0f} semanas de pronóstico a proveedores que "
        f"tardan entre 10 y 17 días. El caso sigue a los {N_TOP} productos más vendidos y a {N_FADED} que dejaron de venderse.\n\n"
    )
    md.append(
        "## La pregunta del negocio\n\n"
        + pregunta(
            "¿Nuestro inventario atiende a los clientes sin inmovilizar dinero de más, y qué rompe ese equilibrio?"
        )
    )
    md.append("## Los indicadores\n\n")
    md.append(
        tiles(
            e,
            H,
            [
                "fill_rate",
                "otif",
                "stockout_rate",
                "days_of_cover",
                "inventory_turnover",
                "obsolescence_share",
                "wape",
                "mape",
                "forecast_bias",
            ],
        )
    )
    md.append(
        "El servicio (unidades atendidas, pedidos completos, quiebres) y el dinero inmovilizado (cobertura, rotación, "
        "inventario sin movimiento) tiran en sentidos opuestos. El pronóstico, y sobre todo su **sesgo**, está antes de ambos.\n\n"
    )

    md.append("## Lo que encontramos\n\n")
    fig = charts.bar(
        list(cats.index), cats.values,
        conclusion=f"Se despacha {pct(H['fill_rate'].value)} de las unidades, pero solo {pct(H['otif'].value)} de los pedidos llega "
        f"completo y a tiempo; la falla más común es «{top_fail.lower()}»",
        subtitle=f"Pedidos según cómo llegaron, {periodo} (cada pedido tiene en promedio {order_size:.1f} líneas de estos productos)",
        pct=True, text=[pct(x, 1) for x in cats.values],
        colors=[theme.STATUS["green"] if c == "Completo y a tiempo" else (theme.HIGHLIGHT if c == top_fail else theme.CONTEXT) for c in cats.index],
    )  # fmt: skip
    fig.update_xaxes(range=[0, 110])
    md.append(
        charts.to_html(
            fig,
            height=320,
            table=pd.DataFrame(
                {"Cómo llegó": cats.index, "Pedidos": [pct(v, 1) for v in cats.values]}
            ),
        )
    )
    md.append(
        f"Las unidades atendidas cuentan **unidades**; «completos y a tiempo» cuenta **pedidos**. Con {order_size:.1f} líneas "
        "por pedido, una sola línea incompleta arruina el pedido entero: por eso los dos indicadores cuentan historias tan distintas.\n\n"
    )

    colors = [
        theme.SECOND if x < lo_band else theme.HIGHLIGHT if x > hi_band else theme.CONTEXT
        for x in mb["value"]
    ]
    fig = go.Figure(go.Bar(x=[mes(m) for m in mb["m"]], y=mb["value"] * 100, marker_color=colors,
                           hovertemplate="%{x}: %{y:+.1f} %<extra></extra>"))  # fmt: skip
    charts.add_band(fig, lo_band, hi_band, pct=True)
    fig.add_hline(y=0, line=dict(color=theme.INK_2, width=1))
    charts.annotate(
        fig,
        mes(lowest["m"]),
        lowest["value"] * 100,
        f"se queda corto {lowest['value'] * 100:+.0f} %<br>→ faltan productos",
        ay=40,
    )
    charts.annotate(
        fig,
        mes(highest["m"]),
        highest["value"] * 100,
        f"se pasa {highest['value'] * 100:+.0f} %<br>→ sobra inventario",
        ay=-40,
    )
    fig.update_layout(title=theme.title(
        f"El promedio de {MA_WEEKS} semanas llega tarde a la temporada: {lowest['value'] * 100:+.0f} % en {mes(lowest['m'])}, "
        f"{highest['value'] * 100:+.0f} % en {mes(highest['m'])}",
        f"Sesgo del pronóstico por mes (pronóstico menos venta, sobre la venta); franja verde = ± {hi_band * 100:.0f} %; naranja = se queda corto, azul = se pasa"))  # fmt: skip
    fig.update_yaxes(ticksuffix=" %", tickformat="+.0f", rangemode="normal")
    md.append(charts.to_html(fig, height=380))

    fig = charts.line(
        [fecha(w) for w in sw["semana"]], sw["value"],
        conclusion=f"Los quiebres llegan a {pct(peak['value'])} en la semana del {fecha(peak['semana'])}; "
        + (f"{pct(under_share)} de los días sin inventario caen en meses en que el pronóstico se quedó corto"
           if under_share >= 0.5 else f"solo {pct(under_share)} caen en meses en que el pronóstico se quedó corto: el resto es variación de la demanda"),
        subtitle="De cada 100 días-producto activos, en cuántos el producto terminó el día sin inventario, por semana",
        name="Quiebres", pct=True,
    )  # fmt: skip
    charts.add_target(
        fig,
        e.catalog["stockout_rate"].target,
        f"Meta {pct(e.catalog['stockout_rate'].target)}",
        pct=True,
    )
    md.append(charts.to_html(fig, height=340))

    f = fc12[fc12["actual_units"] > 0].copy()
    f["ape"] = (f["actual_units"] - f["forecast_units"]).abs() / f["actual_units"]
    labels = ["1 a 9 unidades", "10 a 49 unidades", "50 a 199 unidades", "200 o más unidades"]
    f["tam"] = pd.cut(f["actual_units"], [0, 9, 49, 199, float("inf")], labels=labels)
    acc = f.groupby("tam", observed=False).agg(filas=("ape", "size"), error=("ape", "mean"))
    small = f["actual_units"] < 50
    contrib = f.loc[small, "ape"].sum() / f["ape"].sum()
    fig = charts.bar(
        labels, acc["error"].values,
        conclusion=f"El error porcentual promedio dice {pct(H['mape'].value)} y el ponderado por volumen {pct(H['wape'].value)}: "
        f"las semanas con menos de 50 unidades son {pct(small.mean())} de los casos y aportan {pct(contrib)} del error promedio",
        subtitle="Error porcentual promedio de cada producto-semana, según cuánto se vendió esa semana",
        highlight={labels[0]}, pct=True, horizontal=False, text=[pct(x) for x in acc["error"]],
    )  # fmt: skip
    md.append(
        charts.to_html(
            fig,
            height=380,
            table=pd.DataFrame(
                {
                    "Venta de la semana": labels,
                    "Producto-semanas": acc["filas"].values,
                    "Error promedio": [pct(v) for v in acc["error"]],
                }
            ),
        )
    )
    md.append(
        "El error porcentual promedio le da el mismo voto a cada producto-semana: en una semana de 5 unidades, fallar por 5 "
        "es un error de 100 %. El error ponderado pesa por unidades, que es lo que sienten el inventario y el servicio.\n\n"
    )

    buckets = [
        "30 días o menos",
        "31 a 90 días",
        f"91 a {age_limit} días",
        f"más de {age_limit} días",
    ]
    snap2 = snap.assign(
        tramo=pd.cut(
            snap["days_since_last_movement"], [-1, 30, 90, age_limit, 10**6], labels=buckets
        )
    )
    val = snap2.groupby("tramo", observed=False)["on_hand_value"].sum()
    fig = charts.bar(
        buckets, val.values,
        conclusion=f"{pct(H['obsolescence_share'].value)} del valor del inventario no se vende hace más de {age_limit} días; "
        f"{faded_old} de esos {len(old)} productos son artículos que dejaron de venderse",
        subtitle=f"Valor del inventario a costo según los días desde la última venta, al {fecha(end)}",
        highlight={buckets[-1]}, horizontal=False, decimals=0, text=[n(x) for x in val.values],
    )  # fmt: skip
    md.append(charts.to_html(fig, height=340))

    last = daily[daily["date"] >= end - pd.Timedelta(days=55)]
    best = snap.loc[snap["sku_group"].eq("Más vendido"), "sku"]
    cover = pd.Series(
        {s: e.compute("days_of_cover", last[last["sku"].eq(s)]) for s in best}
    ).replace(float("inf"), 999)
    g_lo, g_hi = e.catalog["days_of_cover"].thresholds["green"]
    low_n, high_n = int((cover < g_lo).sum()), int((cover > g_hi).sum())
    fig = go.Figure(go.Histogram(x=cover.clip(upper=120), xbins=dict(start=0, size=5), marker_color=theme.CONTEXT_DARK,
                                 hovertemplate="%{x} días: %{y} productos<extra></extra>"))  # fmt: skip
    charts.add_band(fig, g_lo, g_hi, axis="x")
    fig.add_annotation(
        x=(g_lo + g_hi) / 2,
        y=1,
        yref="paper",
        text="franja meta",
        showarrow=False,
        font=dict(color=theme.INK_2),
    )
    fig.update_layout(title=theme.title(
        f"Solo {len(cover) - low_n - high_n} de {len(cover)} productos más vendidos están entre {g_lo:.0f} y {g_hi:.0f} días de cobertura: "
        f"{low_n} por debajo y {high_n} por encima",
        f"Días de cobertura por producto al {fecha(end)} (con la demanda de las últimas 8 semanas; más de 120 se muestra como 120)"))  # fmt: skip
    fig.update_xaxes(title_text="días de cobertura")
    fig.update_yaxes(title_text="productos")
    md.append(charts.to_html(fig, height=340))
    md.append(
        "Un solo número de cobertura para toda la tienda compensa los dos extremos entre sí: por eso el catálogo lo define con una franja y lo muestra como distribución.\n\n"
    )

    md.append(
        f"**La historia completa.** El pronóstico mira hacia atrás: antes de la temporada se queda corto y faltan productos; "
        f"después de la temporada sigue alto y sobra inventario, que termina sin moverse. Al {fecha(end)}, {len(old)} productos "
        f"no se venden hace más de {age_limit} días.\n\n"
    )
    md.append("## Qué decidimos\n\n")
    rows = [
        ("Pronosticar los productos de temporada con las mismas semanas del año anterior y su tendencia, desde septiembre.", "Planificador de demanda", fecha(end + pd.Timedelta(days=30))),
        ("Anticipar el inventario de los productos de temporada más vendidos antes del pico, según el nuevo pronóstico y el plazo del proveedor.", "Planificador de abastecimiento", fecha(end + pd.Timedelta(days=60))),
        (f"Liquidar, agrupar o devolver los {len(old)} productos sin ventas en más de {age_limit} días y dejar de pedirlos.", "Controlador de inventarios", fecha(end + pd.Timedelta(days=30))),
        (f"Separar las fallas de los pedidos por responsable: lo incompleto es de planificación y lo tardío de logística. Hoy la más común es «{top_fail.lower()}».", "Jefe de logística", fecha(end + pd.Timedelta(days=30))),
    ]  # fmt: skip
    if under_share < 0.5:
        rows.append(
            (
                "Calcular el inventario de seguridad de cada producto según la variación de su demanda, en lugar de 5 semanas para todos.",
                "Planificador de abastecimiento",
                fecha(end + pd.Timedelta(days=45)),
            )
        )
    md.append(decisiones(rows))
    md.append("## Cómo lo seguimos midiendo\n\n")
    md.append(seguimiento(e, [
        ("forecast_bias", "Cada mes, por tipo de producto (avisa antes)", "Fuera de ± 10 % en un tipo de producto"),
        ("days_of_cover", "Cada semana, por producto", "Menos de 7 días en un producto principal: acelerar el pedido"),
        ("otif", "Cada semana, separando incompletos y tardíos", "Menos de 80 % dos semanas seguidas"),
        ("stockout_rate", "Cada semana", "Más de 6 % en temporada"),
        ("obsolescence_share", "Cada mes", "Más de 10 % del valor del inventario"),
        ("wape", "Cada mes", "Más de 45 %"),
    ]))  # fmt: skip
    md.append(
        detalle_tecnico(f"""
- Demanda: {manifest["transactions"]["name"]} ({manifest["transactions"]["origin"]}). {manifest["transactions"]["note"]}.
- Inventario, pronóstico y entregas: simulación con semilla fija (ver Fuentes de datos). Pronóstico = promedio móvil de {MA_WEEKS} semanas; pedido hasta {ORDER_UP_TO_WEEKS:.0f} semanas; demora del proveedor 10 a 17 días; lo que no hay en inventario se pierde.
- Tablas `order_lines`, `inventory_daily`, `inventory_snapshot`, `forecast`; periodo de las tarjetas: {periodo}.
- Pedidos completos y a tiempo: todas las líneas con `qty_shipped >= qty_ordered` y `delivered_date <= promised_date`.
- Quiebres: solo días-producto con `active = True` (entre la primera y la última demanda del producto).
- Solo semanas y meses completos en el pronóstico.
""")
    )
    return "\n".join(md)
