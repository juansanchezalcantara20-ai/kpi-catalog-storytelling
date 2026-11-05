"""Second presentation layer: an interactive KPI dashboard (one self-contained HTML page, in Spanish).

The story pages explain *why*; the dashboard is the weekly monitoring view. It opens with the
management summary (value at stake, the three most expensive alerts and the "¿y si…?" simulator),
then every KPI of the catalog as a card (value, status, target, sparkline with the target) with
an accessible tooltip, combinable filters by rubro (sector), tema (theme) and status, kept in the
address (#/rubro/mineria/tema/mantenimiento), and a detail panel: the trend with the target
and alert zones, a breakdown by group and a drill-down (click a bar to filter the trend).
Card values come from `headline()` and money from `valor.get_valores()`, the same functions the
story pages use, so the numbers always agree (tested). Output: docs/dashboard/index.html.
"""

from __future__ import annotations

import html
import json
import math
from typing import Any

import pandas as pd

from .catalog import rubros_config
from .data.pipeline import load_tables
from .engine import Engine, format_threshold, format_value
from .formulas.customers import retention_series
from .paths import DOCS_DIR
from .site.common import status_rule
from .site.current import fecha, headline, mes, trimestre
from .valor import get_valores, monthly_series, top_alertas, total_anio
from .viz import theme

PAIS = "Perú"


def _sector_trend(
    e: Engine, kpi: str, df: pd.DataFrame, col: str, xfmt, label: str, group_label: str = "por país"
) -> dict[str, Any]:
    """Trend of the reference group (Peru) plus a breakdown by country with one trend each (drill-down)."""
    f = df[df["country"].eq(PAIS)]
    r = e.compute_by(kpi, f, col).dropna(subset=["value"])
    last = sorted(f[col].unique())[-1]
    g = e.compute_by(kpi, df[df[col].eq(last)], "country").dropna(subset=["value"])
    trends = {
        str(name): {"x": [xfmt(v) for v in sub[col]], "y": sub["value"].tolist(), "n": []}
        for name, sub in e.compute_by(kpi, df, ["country", col])
        .dropna(subset=["value"])
        .groupby("country")
    }
    return {
        "kind": "time", "label": f"{PAIS}, {label}", "x": [xfmt(v) for v in r[col]], "y": r["value"].tolist(), "n": [], "n_label": "",
        "breakdown": {"label": f"{group_label}, {xfmt(last)}", "groups": [{"name": str(a), "value": b, "n": 0.0} for a, b in zip(g["country"], g["value"], strict=True)],
                      "trends": trends},
    }  # fmt: skip


def sector_series(t: dict[str, pd.DataFrame], e: Engine) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    c = t["creditos"].copy()
    c["month"] = pd.to_datetime(c["month"])
    out["npl_ratio"] = _trend(
        e,
        "npl_ratio",
        c,
        "month",
        "por mes",
        "filas de la cartera",
        group="segment",
        group_label="por segmento",
    )
    months = sorted(c["month"].unique())[12:]
    gr = [e.compute("loan_growth", c[c["month"].le(m)]) for m in months]
    out["loan_growth"] = {
        "kind": "time",
        "label": "por mes, frente a 12 meses antes",
        "x": [mes(m) for m in months],
        "y": gr,
        "n": [],
        "n_label": "",
    }
    en = t["energia_anual"]
    for k in ("renewable_share_elec", "fossil_share_elec", "carbon_intensity_elec"):
        out[k] = _sector_trend(e, k, en, "year", str, "por año")
    s = t["salud_semanal"].copy()
    s["month"] = pd.to_datetime(s["week"]).dt.to_period("M").dt.start_time
    for k in ("vaccination_complete_share", "deaths_per_million_week"):
        out[k] = _sector_trend(e, k, s, "month", mes, "por mes")
    mo = t["moviles_anual"]
    out["mobile_penetration"] = _sector_trend(e, "mobile_penetration", mo, "year", str, "por año")
    pm = mo[mo["country"].eq(PAIS)]
    ys = sorted(pm["year"].unique())[1:]
    out["lines_growth"] = {"kind": "time", "label": f"{PAIS}, por año", "x": [str(y) for y in ys],
                           "y": [e.compute("lines_growth", pm[pm["year"].isin([y - 1, y])]) for y in ys], "n": [], "n_label": ""}  # fmt: skip
    d = t["docentes"]
    rec = d[d["year"] >= d["year"].max() - 2]
    lv = e.compute_by("pupil_teacher_ratio", rec, "level")
    out["pupil_teacher_ratio"] = {"kind": "category", "label": "por nivel, Sudamérica, últimos tres años", "x": lv["level"].tolist(),
                                  "y": lv["value"].tolist(), "n": rec.groupby("level").size().reindex(lv["level"]).astype(float).tolist(), "n_label": "registros"}  # fmt: skip
    v = t["vuelos"]
    hb = e.compute_by("on_time_share", v, "hour_band")
    order = [
        "Madrugada (0 a 6 h)",
        "Mañana (6 a 10 h)",
        "Mediodía (10 a 14 h)",
        "Tarde (14 a 18 h)",
        "Noche (18 a 24 h)",
    ]
    hb = (
        hb.set_index("hour_band")
        .reindex([o for o in order if o in set(hb["hour_band"])])
        .reset_index()
    )
    out["on_time_share"] = {"kind": "category", "label": "por franja horaria de salida", "x": hb["hour_band"].tolist(), "y": hb["value"].tolist(),
                            "n": v.groupby("hour_band").size().reindex(hb["hour_band"]).astype(float).tolist(), "n_label": "vuelos"}  # fmt: skip
    return out


def _month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.to_period("M").dt.start_time


def _complete_months(df: pd.DataFrame, col: str, last_date: pd.Timestamp) -> pd.DataFrame:
    """Drop the last month when the data ends before the month does."""
    if last_date < last_date + pd.offsets.MonthEnd(0):
        return df[df[col] < last_date.to_period("M").start_time]
    return df


def _trend(e: Engine, kpi: str, df: pd.DataFrame, col: str, label: str, n_label: str, count: str | None = None,
           group: str | None = None, group_label: str = "") -> dict[str, Any]:  # fmt: skip
    """Trend by period (+ volume) and, if `group` is given, a breakdown with one trend per group."""
    r = e.compute_by(kpi, df, col).dropna(subset=["value"])
    vol = df.groupby(col)[count].nunique() if count else df.groupby(col).size()
    out: dict[str, Any] = {
        "kind": "time", "label": label, "x": [mes(d) for d in r[col]], "y": r["value"].tolist(),
        "n": [float(vol.get(d, 0)) for d in r[col]], "n_label": n_label,
    }  # fmt: skip
    if group:
        last = sorted(df[col].dropna().unique())[-3:]  # breakdown over the last three periods
        recent = df[df[col].isin(last)]
        g = e.compute_by(kpi, recent, group).dropna(subset=["value"])
        gvol = recent.groupby(group)[count].nunique() if count else recent.groupby(group).size()
        trends = {}
        for name, sub in (
            e.compute_by(kpi, df, [group, col]).dropna(subset=["value"]).groupby(group)
        ):
            v = df[df[group].eq(name)]
            nv = v.groupby(col)[count].nunique() if count else v.groupby(col).size()
            trends[str(name)] = {
                "x": [mes(d) for d in sub[col]],
                "y": sub["value"].tolist(),
                "n": [float(nv.get(d, 0)) for d in sub[col]],
            }
        out["breakdown"] = {
            "label": f"{group_label}, últimos tres meses",
            "groups": [
                {"name": str(a), "value": b, "n": float(gvol.get(a, 0))}
                for a, b in zip(g[group], g["value"], strict=True)
            ],
            "trends": trends,
        }
    return out


def series(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    snap = pd.Timestamp(manifest["tickets"]["snapshot"])
    limit = (snap + pd.Timedelta(minutes=1)).to_period("M").start_time
    tk = t["tickets"]
    tk_c = tk[tk["created_month"] < limit]
    res = tk_c[tk_c["status"].eq("resolved")]
    out["first_response_time"] = _trend(
        e,
        "first_response_time",
        tk_c,
        "created_month",
        "por mes de apertura",
        "solicitudes",
        group="queue",
        group_label="por equipo",
    )
    for k in ("resolution_time", "sla_compliance", "first_contact_resolution", "reopen_rate"):
        out[k] = _trend(
            e,
            k,
            res,
            "resolved_month",
            "por mes de cierre",
            "solicitudes cerradas",
            group="queue",
            group_label="por equipo",
        )
    bk = monthly_series("service", t, e, manifest)
    open_ = tk[tk["status"].eq("open")]
    gb = e.compute_by("backlog_aged_share", tk, "queue")
    out["backlog_aged_share"] = {
        "kind": "time", "label": "al cierre de cada mes", "x": [mes(d) for d in bk.index], "y": bk.tolist(), "n": [], "n_label": "",
        "breakdown": {"label": "por equipo, a la fecha de corte", "trends": {},
                      "groups": [{"name": q, "value": v, "n": float((open_["queue"] == q).sum())} for q, v in zip(gb["queue"], gb["value"], strict=True)]},
    }  # fmt: skip

    ap, wo = t["asset_periods"], t["work_orders"]
    out["mtbf"] = _trend(
        e, "mtbf", ap, "month", "por mes", "fallas", group="asset_id", group_label="por máquina"
    )
    out["availability"] = _trend(
        e,
        "availability",
        ap,
        "month",
        "por mes",
        "registros",
        group="asset_id",
        group_label="por máquina",
    )
    corr = wo[wo["wo_type"].eq("corrective")]
    out["mttr"] = _trend(
        e,
        "mttr",
        corr,
        "month",
        "por mes",
        "reparaciones",
        group="asset_id",
        group_label="por máquina",
    )
    pm = wo[wo["wo_type"].eq("preventive")].assign(due_month=lambda d: _month(d["due_date"]))
    out["pm_compliance"] = _trend(
        e,
        "pm_compliance",
        pm,
        "due_month",
        "por mes programado",
        "preventivos",
        group="asset_id",
        group_label="por máquina",
    )
    out["planned_work_share"] = _trend(
        e,
        "planned_work_share",
        wo,
        "month",
        "por mes",
        "órdenes",
        group="asset_id",
        group_label="por máquina",
    )

    daily, ol, fc, snapi = (
        t["inventory_daily"],
        t["order_lines"],
        t["forecast"],
        t["inventory_snapshot"],
    )
    end = daily["date"].max()
    grp = snapi.set_index("sku")["sku_group"]
    ol = _complete_months(ol.assign(m=_month(ol["order_date"]), grupo=ol["sku"].map(grp)), "m", end)
    out["fill_rate"] = _trend(
        e,
        "fill_rate",
        ol,
        "m",
        "por mes del pedido",
        "pedidos",
        count="order_id",
        group="grupo",
        group_label="por grupo de productos",
    )
    out["otif"] = _trend(
        e,
        "otif",
        ol,
        "m",
        "por mes del pedido",
        "pedidos",
        count="order_id",
        group="grupo",
        group_label="por grupo de productos",
    )
    d = _complete_months(
        daily.assign(m=_month(daily["date"]), grupo=daily["sku"].map(grp)), "m", end
    )
    for k in ("inventory_turnover", "stockout_rate", "days_of_cover"):
        out[k] = _trend(
            e,
            k,
            d,
            "m",
            "por mes",
            "productos",
            count="sku",
            group="grupo",
            group_label="por grupo de productos",
        )
    f = _complete_months(fc.assign(m=_month(fc["week"]), grupo=fc["sku"].map(grp)), "m", end)
    for k in ("mape", "wape", "forecast_bias"):
        out[k] = _trend(
            e,
            k,
            f,
            "m",
            "por mes",
            "productos",
            count="sku",
            group="grupo",
            group_label="por grupo de productos",
        )
    go_ = e.compute_by("obsolescence_share", snapi, "sku_group")
    out["obsolescence_share"] = {"kind": "category", "label": "valor del inventario a la última fecha, por grupo de productos", "x": go_["sku_group"].tolist(),
                                 "y": go_["value"].tolist(), "n": snapi.groupby("sku_group").size().reindex(go_["sku_group"]).tolist(), "n_label": "productos"}  # fmt: skip

    cs, rfm, sv = t["customer_sales"], t["customer_rfm"], t["survey"]
    period = e.catalog["retention_rate"].params["period"]
    seg = rfm.set_index("customer_id")["segment"]
    last_q = cs["invoice_date"].max().to_period("Q")
    drop_last = cs["invoice_date"].max() < last_q.end_time.normalize()

    def ret_of(df: pd.DataFrame) -> pd.Series:
        r = retention_series(df, period)
        return r.drop(index=str(last_q), errors="ignore") if drop_last else r

    ret = ret_of(cs)
    trends, groups = {}, []
    cs_seg = cs.assign(seg=cs["customer_id"].map(seg))
    for name, sub in cs_seg.dropna(subset=["seg"]).groupby("seg"):
        r = ret_of(sub)
        if len(r):
            trends[name] = {"x": [trimestre(q) for q in r.index], "y": r.tolist(), "n": []}
            groups.append(
                {"name": name, "value": float(r.iloc[-1]), "n": float(sub["customer_id"].nunique())}
            )
    out["retention_rate"] = {"kind": "time", "label": "por trimestre", "x": [trimestre(q) for q in ret.index], "y": ret.tolist(), "n": [], "n_label": "",
                             "breakdown": {"label": "por tipo de cliente, último trimestre", "groups": groups, "trends": trends}}  # fmt: skip
    first = cs.groupby("customer_id")["invoice_date"].transform("min").dt.year.astype(str)
    rp = e.compute_by(
        "repeat_purchase_rate", cs.assign(cohorte="Primera compra en " + first), "cohorte"
    )
    out["repeat_purchase_rate"] = {
        "kind": "category",
        "label": "por año de primera compra",
        "x": rp["cohorte"].tolist(),
        "y": rp["value"].tolist(),
        "n": [],
        "n_label": "clientes",
    }
    rs = monthly_series("customers", t, e, manifest)
    segm = rfm.groupby("segment")["monetary"].sum().sort_values(ascending=False)
    out["revenue_at_risk_share"] = {
        "kind": "time", "label": "al cierre de cada mes", "x": [mes(d) for d in rs.index], "y": rs.tolist(), "n": [], "n_label": "",
        "breakdown": {"label": "parte del ingreso por tipo de cliente", "share": True, "trends": {},
                      "groups": [{"name": a, "value": float(b / segm.sum()), "n": float((rfm["segment"] == a).sum())} for a, b in segm.items()]},
    }  # fmt: skip
    out["nps"] = _trend(
        e,
        "nps",
        sv.assign(m=_month(sv["responded_at"])),
        "m",
        "por mes de respuesta",
        "respuestas",
        group="segment",
        group_label="por tipo de cliente",
    )

    dq = t["dq_results"]
    for dim in ("completeness", "uniqueness", "validity", "timeliness"):
        sub = dq[dq["dimension"].eq(dim) & (dq["total"] > 0)]
        out[f"dq_{dim}"] = {"kind": "category", "label": "por conjunto de datos", "x": sub["label"].str.replace(r" \(.*\)", "", regex=True).tolist(),
                            "y": sub["value"].tolist(), "n": sub["total"].tolist(), "n_label": "registros revisados"}  # fmt: skip
    out.update(sector_series(t, e))
    return out


def _clean(o: Any) -> Any:
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else round(o, 6)
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def payload(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> dict[str, Any]:
    heads = headline(t, e, manifest)
    sers = series(t, e, manifest)
    unavailable = set((manifest.get("tickets") or {}).get("unavailable_kpis", []))
    kpis = []
    for k in e.catalog:
        h = heads[k.id]
        v = h.value
        s = sers.get(k.id, {"kind": "none", "label": "", "x": [], "y": []})
        if k.id in unavailable:
            s = {
                "kind": "none",
                "label": "la fuente pública no registra este dato",
                "x": [],
                "y": [],
            }
        status = e.status(k.id, v)
        kpis.append(
            {
                "id": k.id, "name": k.name, "case": k.case, "case_title": e.catalog.cases[k.case]["title"], "rubros": k.rubros, "tema": k.tema, "unit": k.unit, "direction": k.direction, "value": v,
                "display": format_value(k, v) if not math.isnan(v) else "Sin dato", "period": h.note or h.period,
                "status": status, "rule": status_rule(k, status), "target": format_threshold(k, with_alert=False),
                "target_full": format_threshold(k), "target_value": k.target, "green": k.thresholds["green"],
                "amber": k.thresholds["amber"], "question": k.question, "meaning": k.meaning, "calculation": k.calculation,
                "target_why": k.target_why, "decision": k.decision, "balance": k.balance, "how_to_read": k.how_to_read,
                "misreadings": k.misreadings, "owner": k.owner, "series": s,
            }
        )  # fmt: skip
    vals = get_valores(t, e, manifest)
    casos = [
        {
            "caso": v.caso, "titulo": v.titulo, "soles_mes": v.soles_mes, "soles_anio": v.soles_anio, "horas_mes": v.horas_mes,
            "resumen": v.resumen_brecha, "accion": v.accion, "responsable": v.responsable, "fecha": v.fecha,
            "componentes": [{c2: getattr(c, c2) for c2 in ("kpi", "nombre", "valor", "meta", "direccion", "unidad_pct", "base", "unidad", "costo_unitario", "horas_unitarias")}
                            for c in v.componentes],
        }
        for v in vals.values()
    ]  # fmt: skip
    origins = {manifest[key]["origin"] for key in ("tickets", "process_data", "transactions")}
    return _clean(
        {
            "cases": {c: d["title"] for c, d in e.catalog.cases.items()},
            "case_rubros": {c: d["rubros"] for c, d in e.catalog.cases.items()},
            "rubros": {r: d["nombre"] for r, d in rubros_config()["rubros"].items()},
            "temas": {r: d["nombre"] for r, d in rubros_config()["temas"].items()},
            "kpis": kpis,
            "valor": {
                "casos": casos,
                "top": [v.caso for v in top_alertas(vals)],
                "total_anio": total_anio(vals),
            },
            "data_note": "datos públicos reales y simulaciones"
            if "real" in origins
            else "datos simulados: muestran el método, no describen una empresa real",
            "built": fecha(manifest["generated_at"][:10]),
        }
    )


PAGE = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tablero de indicadores</title>
<script src="../assets/js/plotly.min.js"></script>
<script src="../assets/js/plotly-es.js"></script>
<style>
:root {
  --surface: __SURFACE__; --page: #f4f4f1; --ink: __INK__; --ink-2: __INK2__; --muted: __MUTED__;
  --grid: __GRID__; --accent: __HIGHLIGHT__; --good: __GOOD__; --watch: __WATCH__; --act: __ACT__;
}
* { box-sizing: border-box; }
html, body { overflow-x: hidden; }
body { margin: 0; background: var(--page); color: var(--ink); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { background: #1c5cab; color: #fff; padding: 14px 20px; display: flex; flex-wrap: wrap; gap: 6px 20px; align-items: baseline; }
header h1 { font-size: 19px; margin: 0; font-weight: 650; }
header p { margin: 0; opacity: .9; font-size: 13px; }
header a { color: #fff; margin-left: auto; font-size: 13px; }
main { padding: 16px 20px 32px; max-width: 1400px; margin: 0 auto; }
h2 { font-size: 16px; margin: 6px 0 10px; }
.resumen { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 12px; margin-bottom: 14px; }
.total { background: var(--surface); border: 1px solid var(--grid); border-left: 6px solid var(--act); border-radius: 8px; padding: 12px 14px; }
.total .big { font-size: 28px; font-weight: 700; line-height: 1.15; }
.alertas { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
.alerta { background: var(--surface); border: 1px solid var(--grid); border-radius: 8px; padding: 10px 12px; font-size: 13px; text-align: left; font: inherit; cursor: pointer; }
.alerta .monto { font-size: 18px; font-weight: 700; }
.alerta .quien { color: var(--ink-2); font-size: 12px; margin-top: 4px; }
.sim-box { background: var(--surface); border: 1px solid var(--grid); border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; }
.simulador label { display: block; font-size: 12.5px; font-weight: 600; margin-top: 6px; }
.simulador input[type=range] { width: 100%; }
.simulador input[type=number] { width: 7rem; }
.simulador .fila { display: flex; flex-wrap: wrap; gap: 4px 18px; }
.simulador .resultado { font-size: 16px; font-weight: 700; }
.aviso-supuestos { font-size: 12px; color: var(--ink-2); font-style: italic; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; margin-bottom: 14px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid var(--grid); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 5px 12px; cursor: pointer; font: inherit; font-size: 13px; }
.filtros { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; }
.filtros select { font: inherit; font-size: 13px; padding: 5px 8px; border: 1px solid var(--grid); border-radius: 8px; background: var(--surface); color: var(--ink); max-width: 100%; }
.chip[aria-pressed="true"] { background: var(--ink); color: #fff; border-color: var(--ink); }
.summary { font-size: 13px; color: var(--ink-2); }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); gap: 16px; align-items: start; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }
.card { text-align: left; font: inherit; color: inherit; background: var(--surface); border: 1px solid var(--grid); border-left: 5px solid var(--grid); border-radius: 6px; padding: 9px 11px; cursor: pointer; display: flex; flex-direction: column; gap: 2px; min-height: 150px; }
.card:hover, .card:focus-visible { box-shadow: 0 1px 6px rgba(0,0,0,.12); }
.card[aria-current="true"] { outline: 2px solid var(--accent); outline-offset: 1px; }
.card.green { border-left-color: var(--good); } .card.amber { border-left-color: var(--watch); } .card.red { border-left-color: var(--act); }
.card .case { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; }
.card .name { font-size: 12.5px; color: var(--ink-2); line-height: 1.25; }
.card .value { font-size: 24px; font-weight: 650; line-height: 1.15; }
.card .status { font-size: 12px; color: var(--ink-2); text-decoration: underline dotted; text-underline-offset: 2px; width: fit-content; }
.card .period { font-size: 12px; color: var(--muted); }
.card svg { margin-top: auto; max-width: 100%; }
.detail { background: var(--surface); border: 1px solid var(--grid); border-radius: 6px; padding: 14px 16px; position: sticky; top: 12px; }
.detail h2 { margin: 0 0 2px; font-size: 18px; }
.detail .q { margin: 0 0 8px; color: var(--ink-2); }
.detail .big { font-size: 30px; font-weight: 650; }
.detail .meta { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--ink-2); margin: 2px 0 6px; }
.detail h3 { font-size: 13px; margin: 12px 0 4px; text-transform: uppercase; letter-spacing: .03em; color: var(--ink-2); }
.detail ul { margin: 0; padding-left: 18px; } .detail li { margin: 2px 0; }
.detail .links a { color: var(--accent); margin-right: 14px; font-size: 13px; }
.grafico { width: 100%; height: 320px; }
.drill { font-size: 13px; color: var(--ink-2); margin: 4px 0; }
.drill button { font: inherit; font-size: 12px; margin-left: 8px; cursor: pointer; }
details.datos { font-size: 12px; margin: 2px 0 10px; } details.datos table { border-collapse: collapse; } details.datos td, details.datos th { padding: 2px 8px; border-bottom: 1px solid var(--grid); text-align: left; }
.nodata { color: var(--ink-2); font-style: italic; }
.kpi-tip { position: fixed; z-index: 1000; max-width: min(340px, calc(100vw - 16px)); width: max-content; background: #fff; color: #0b0b0b; border: 1px solid #c3c2b7; border-radius: 8px; box-shadow: 0 6px 24px rgba(0,0,0,.16); padding: 10px 12px; font-size: 12.5px; line-height: 1.4; pointer-events: none; }
.kpi-tip[hidden] { display: none; }
.kpi-tip b { display: block; margin-bottom: 4px; } .kpi-tip dl { margin: 0; } .kpi-tip dt { font-weight: 650; color: #52514e; margin-top: 4px; } .kpi-tip dd { margin: 0; }
footer { color: var(--muted); font-size: 12px; margin-top: 18px; }
@media (max-width: 960px) { .layout, .resumen { grid-template-columns: 1fr; } .detail { position: static; } }
</style>
</head>
<body>
<header>
  <h1>Tablero de indicadores</h1>
  <p>__NKPI__ indicadores · __DATA_NOTE__ · actualizado el __BUILT__</p>
  <a href="../">← Volver a las historias</a>
</header>
<main>
  <h2>Resumen para gerencia</h2>
  <section class="resumen" aria-label="Resumen para gerencia">
    <div class="total" id="total"></div>
    <div class="alertas" id="alertas"></div>
  </section>
  <section class="sim-box" aria-label="Simulador">
    <label for="sim-caso"><b>¿Y si…?</b> Elija un área: </label>
    <select id="sim-caso"></select>
    <div id="sims"></div>
  </section>
  <h2>Indicadores</h2>
  <div class="toolbar">
    <div class="filtros"><label for="f-rubro">Rubro</label><select id="f-rubro"></select>
    <label for="f-tema">Tema</label><select id="f-tema"></select></div>
    <div class="chips" id="estados" role="group" aria-label="Semáforo"></div>
    <span class="summary" id="resumen" aria-live="polite"></span>
  </div>
  <p class="summary">Pase el mouse (o toque) una tarjeta para ver qué mide, cómo se calcula y por qué esa meta; haga clic para ver su tendencia y su desglose.</p>
  <div class="layout">
    <section class="grid" id="tarjetas" aria-label="Tarjetas de indicadores"></section>
    <section class="detail" id="detalle" aria-live="polite"></section>
  </div>
  <div id="tips"></div>
  <footer>Semáforo: 🟢 En meta · 🟡 Vigilar · 🔴 Actuar, siempre frente a la meta del catálogo y nunca frente a un promedio.
  Cada tarjeta muestra el mismo valor que su historia y su ficha del catálogo. Las tendencias usan solo periodos completos.
  Montos en soles con supuestos ilustrativos; cámbielos con los de su empresa en el simulador.</footer>
</main>
<script>
const DATA = __PAYLOAD__;
const ICON = {green: "🟢", amber: "🟡", red: "🔴", "n/a": "⚪"};
const WORD = {green: "En meta", amber: "Vigilar", red: "Actuar", "n/a": "Sin dato"};
const COLOR = {green: "__GOOD__", amber: "__WATCH__", red: "__ACT__", "n/a": "__CONTEXT__"};
const state = {rubro: "all", tema: "all", status: "all", kpi: null, group: null};
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const num = (x, d = 0) => x.toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d}).replace(/,/g, " ");
const soles = x => "S/ " + num(Math.round(x));

function isPct(k) { return k.unit === "percent"; }
function suffix(k) { return isPct(k) ? " %" : ({hours: " h", days: " días", times_per_year: " veces al año", g_per_kwh: " g por kWh", per_million: " por millón", per_100: " por cada 100", ratio: " alumnos por docente"}[k.unit] || ""); }
function axisSuffix(k) { return isPct(k) ? " %" : ({hours: " h", days: " días"}[k.unit] || ""); }
function fmt(k, v) {
  if (v === null || v === undefined) return "sin dato";
  if (k.unit === "score") return (v >= 0 ? "+" : "") + v.toFixed(0);
  return num(v * (isPct(k) ? 100 : 1), 1) + suffix(k);
}
function grade(k, v) {
  if (v === null || v === undefined) return "n/a";
  if (k.direction === "higher_is_better") return v >= k.green ? "green" : v >= k.amber ? "amber" : "red";
  if (k.direction === "lower_is_better") return v <= k.green ? "green" : v <= k.amber ? "amber" : "red";
  return (v >= k.green[0] && v <= k.green[1]) ? "green" : (v >= k.amber[0] && v <= k.amber[1]) ? "amber" : "red";
}
function hoverText(k, label, v, n, nLabel) {
  if (v === null || v === undefined) return label + " · sin dato";
  const st = grade(k, v);
  const parts = [label, fmt(k, v), "Meta " + k.target, ICON[st] + " " + WORD[st]];
  if (k.direction !== "target_range") {
    const d = v - k.target_value;
    if (Math.abs(d) > 1e-9) parts.push((isPct(k) ? num(Math.abs(d) * 100, 1) + " puntos" : fmt(k, Math.abs(d))) + (d > 0 ? " por encima" : " por debajo") + " de la meta");
  }
  if (n && nLabel) parts.push(num(n) + " " + nLabel);
  return parts.join(" · ");
}

// ---------------------------------------------------------------- resumen para gerencia
function resumen() {
  const V = DATA.valor, byCase = Object.fromEntries(V.casos.map(c => [c.caso, c]));
  document.getElementById("total").innerHTML = `<div>Valor en juego</div><div class="big" data-valor-total="${Math.round(V.total_anio)}">${soles(V.total_anio)} al año</div>
    <div>repartidos en ${V.casos.length} áreas. Supuestos ilustrativos; cámbielos con los de su empresa.</div>`;
  document.getElementById("alertas").innerHTML = V.top.map((id, i) => { const c = byCase[id]; return `
    <button class="alerta" data-case="${c.caso}" data-valor-anio="${Math.round(c.soles_anio)}"><div>${i + 1} · ${esc(c.titulo)}</div>
    <div class="monto">${soles(c.soles_mes)} al mes</div><div>${esc(c.resumen)}</div>
    <div class="quien"><b>Acción:</b> ${esc(c.accion)}<br><b>Responsable:</b> ${esc(c.responsable)} · <b>Fecha:</b> ${esc(c.fecha)}</div></button>`; }).join("");
  const sel = document.getElementById("sim-caso");
  sel.innerHTML = V.casos.map(c => `<option value="${c.caso}">${esc(c.titulo)} · ${soles(c.soles_mes)} al mes</option>`).join("");
  document.getElementById("sims").innerHTML = V.casos.map(c => `<div class="simulador" data-sim="${c.caso}" ${c.caso === V.top[0] ? "" : "hidden"}><script type="application/json">${JSON.stringify({caso: c.caso, componentes: c.componentes}).replace(/</g, "\\u003c")}<\/script></div>`).join("");
  sel.value = V.top[0];
  sel.addEventListener("change", () => document.querySelectorAll("#sims .simulador").forEach(d => d.hidden = d.dataset.sim !== sel.value));
}

// ---------------------------------------------------------------- tarjetas
function sparkline(k) {
  const s = k.series;
  if (!s || s.kind !== "time" || s.y.length < 2) return "";
  const ys = s.y.filter(v => v !== null).concat([k.target_value]), w = 180, h = 34;
  const lo = Math.min(...ys), hi = Math.max(...ys), span = (hi - lo) || 1;
  const Y = v => h - 3 - (v - lo) / span * (h - 6);
  const pts = s.y.map((v, i) => v === null ? null : [i / (s.y.length - 1) * w, Y(v)]).filter(Boolean);
  const last = pts[pts.length - 1], ty = Y(k.target_value);
  return `<svg width="${w}" height="${h}" role="img" aria-label="tendencia con la meta punteada"><line x1="0" x2="${w}" y1="${ty}" y2="${ty}" stroke="__INK2__" stroke-width="1" stroke-dasharray="3 3"/><polyline fill="none" stroke="__CONTEXT_DARK__" stroke-width="1.5" points="${pts.map(p => p.join(",")).join(" ")}"/><circle cx="${last[0]}" cy="${last[1]}" r="3" fill="__HIGHLIGHT__"/></svg>`;
}
function tipHtml(k) {
  return `<div class="kpi-tip" role="tooltip" id="tip-${k.id}" hidden><b>${esc(k.name)}</b><dl>
    <dt>Qué mide</dt><dd>${esc(k.meaning)}</dd><dt>Cómo se calcula</dt><dd>${esc(k.calculation)}</dd>
    <dt>Meta y por qué</dt><dd>${esc(k.target_full)}. ${esc(k.target_why)}</dd><dt>Qué decisión ayuda a tomar</dt><dd>${esc(k.decision)}</dd>
    <dt>Con qué se equilibra</dt><dd>${esc(k.balance)}</dd><dt>Responsable</dt><dd>${esc(k.owner)}</dd></dl></div>
    <div class="kpi-tip" role="tooltip" id="regla-${k.id}" hidden>${esc(k.rule)}</div>`;
}
function chips() {
  const opt = (o, all, cur) => [["all", all], ...Object.entries(o)].map(([id, t]) => `<option value="${id}" ${cur === id ? "selected" : ""}>${esc(t)}</option>`).join("");
  document.getElementById("f-rubro").innerHTML = opt(DATA.rubros, "Todos los rubros", state.rubro);
  document.getElementById("f-tema").innerHTML = opt(DATA.temas, "Todos los temas", state.tema);
  const sts = [["all", "Cualquier estado"], ["red", "🔴 Actuar"], ["amber", "🟡 Vigilar"], ["green", "🟢 En meta"]];
  document.getElementById("estados").innerHTML = sts.map(([id, t]) => `<button class="chip" aria-pressed="${state.status === id}" data-status="${id}">${t}</button>`).join("");
}
function visible() {
  return DATA.kpis.filter(k => (state.rubro === "all" || k.rubros.includes(state.rubro)) && (state.tema === "all" || k.tema === state.tema)
    && (state.status === "all" || k.status === state.status));
}
function hashOf() {
  const p = [];
  if (state.rubro !== "all") p.push("rubro", state.rubro);
  if (state.tema !== "all") p.push("tema", state.tema);
  if (state.status !== "all") p.push("estado", state.status);
  if (state.kpi) p.push("indicador", state.kpi);
  return "#/" + p.join("/");
}
function readHash() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h.startsWith("/")) {
    const p = h.slice(1).split("/");
    for (let i = 0; i + 1 < p.length; i += 2) {
      if (p[i] === "rubro" && p[i + 1] in DATA.rubros) state.rubro = p[i + 1];
      if (p[i] === "tema" && p[i + 1] in DATA.temas) state.tema = p[i + 1];
      if (p[i] === "estado" && ["red", "amber", "green"].includes(p[i + 1])) state.status = p[i + 1];
      if (p[i] === "indicador") state.kpi = p[i + 1];
    }
  } else if (h) {  // older addresses: dominio/estado/indicador
    const p = h.split("/");
    if (["red", "amber", "green"].includes(p[1])) state.status = p[1];
    if (p[2]) state.kpi = p[2];
  }
}
function render() {
  chips();
  const list = visible();
  if (!list.find(k => k.id === state.kpi)) { state.kpi = list.length ? list[0].id : null; state.group = null; }
  document.getElementById("tarjetas").innerHTML = list.map(k => `
    <button class="card ${k.status.replace("/", "")}" data-kpi="${k.id}" aria-current="${k.id === state.kpi}" data-tip aria-describedby="tip-${k.id}">
      <span class="case">${esc(k.case_title)}</span><span class="name">${esc(k.name)}</span><span class="value">${k.display}</span>
      <span class="status" data-tip aria-describedby="regla-${k.id}">${ICON[k.status]} ${WORD[k.status]} · meta ${k.target}</span>
      <span class="period">${esc(k.period)}</span>${sparkline(k)}</button>`).join("") || "<p>Ningún indicador cumple estos filtros.</p>";
  const c = {red: 0, amber: 0, green: 0};
  list.forEach(k => { if (k.status in c) c[k.status]++; });
  const filtro = [state.rubro !== "all" ? DATA.rubros[state.rubro] : "", state.tema !== "all" ? DATA.temas[state.tema] : ""].filter(Boolean).join(" · ");
  document.getElementById("resumen").textContent = `${filtro ? filtro + ": " : ""}${list.length} indicadores · ${c.red} para actuar · ${c.amber} para vigilar · ${c.green} en meta`;
  detail();
  try { history.replaceState(null, "", hashOf()); } catch (e) {}
}

// ---------------------------------------------------------------- detalle
function table(rows, head) {
  return `<details class="datos"><summary>Ver datos</summary><table><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></details>`;
}
function detail() {
  const el = document.getElementById("detalle");
  const k = DATA.kpis.find(x => x.id === state.kpi);
  if (!k) { el.innerHTML = ""; return; }
  const s = k.series, b = s.breakdown;
  el.innerHTML = `<h2>${esc(k.name)}</h2><p class="q">${esc(k.question)}</p>
    <div class="big">${ICON[k.status]} ${k.display}</div>
    <div class="meta"><span>${WORD[k.status]}</span><span>${esc(k.period)}</span><span>Meta ${esc(k.target_full)}</span><span>Responsable: ${esc(k.owner)}</span></div>
    <p>${esc(k.meaning)}</p>
    ${s.kind === "none" ? `<p class="nodata">Sin gráfico: ${esc(s.label)}.</p>` : `<div class="drill" id="drill"></div><div id="g-trend" class="grafico" role="img" aria-label="${esc(k.name)}: tendencia"></div><div id="t-trend"></div>`}
    ${b ? `<div id="g-break" class="grafico" role="img" aria-label="${esc(k.name)}: desglose"></div><div id="t-break"></div>` : ""}
    <h3>Cómo leerlo</h3><p>${esc(k.how_to_read)}</p>
    <h3>Errores comunes de lectura</h3><ul>${k.misreadings.map(m => `<li>${esc(m)}</li>`).join("")}</ul>
    <p class="links"><a href="../cases/${k.case}/">Ver la historia →</a><a href="../catalog/${k.id}/">Ficha completa del indicador →</a></p>`;
  if (s.kind !== "none") drawTrend(k);
  if (b) drawBreak(k);
}
function zones(k, m) {
  const sh = [];
  const add = (lo, hi, col) => sh.push({type: "rect", xref: "paper", x0: 0, x1: 1, y0: lo * m, y1: hi * m, fillcolor: col, line: {width: 0}, layer: "below"});
  const top = isPct(k) ? 1 : Math.max(k.target_value * 3, 1);
  if (k.direction === "higher_is_better") { add(k.green, top, "rgba(12,163,12,0.08)"); add(k.amber, k.green, "rgba(250,178,25,0.14)"); }
  else if (k.direction === "lower_is_better") { add(0, k.green, "rgba(12,163,12,0.08)"); add(k.green, k.amber, "rgba(250,178,25,0.14)"); }
  else { add(k.green[0], k.green[1], "rgba(12,163,12,0.08)"); add(k.amber[0], k.green[0], "rgba(250,178,25,0.14)"); add(k.green[1], k.amber[1], "rgba(250,178,25,0.14)"); }
  return sh;
}
function baseLayout(title) {
  return {margin: {l: 56, r: 16, t: 54, b: 44}, paper_bgcolor: "__SURFACE__", plot_bgcolor: "__SURFACE__", separators: ". ",
    font: {family: "system-ui, -apple-system, Segoe UI, sans-serif", size: 12, color: "__INK2__"},
    title: {text: title, x: 0, xanchor: "left", font: {size: 13, color: "__INK__"}}, showlegend: false, shapes: [], annotations: []};
}
function drawTrend(k) {
  const s = k.series, m = isPct(k) ? 100 : 1, kind = s.kind;
  let x = s.x, y = s.y, n = s.n || [], who = "";
  if (state.group && s.breakdown && s.breakdown.trends[state.group]) { const t = s.breakdown.trends[state.group]; x = t.x; y = t.y; n = t.n || []; who = state.group; }
  document.getElementById("drill").innerHTML = who ? `Mostrando solo «${esc(who)}».<button id="ver-todo">Ver todo</button>` : (s.breakdown && Object.keys(s.breakdown.trends).length ? "Haga clic en una barra del desglose para filtrar la tendencia." : "");
  const vb = document.getElementById("ver-todo"); if (vb) vb.onclick = () => { state.group = null; drawTrend(k); };
  if (kind === "category") {
    const L = baseLayout(`${esc(k.name)} ${s.label}`);
    Plotly.react("g-trend", [{type: "bar", orientation: "h", x: y.map(v => v * m), y: x, marker: {color: y.map(v => COLOR[grade(k, v)])},
      text: y.map(v => fmt(k, v)), textposition: "outside", cliponaxis: false, customdata: x.map((g, i) => hoverText(k, g, y[i], n[i], s.n_label)), hovertemplate: "%{customdata}<extra></extra>"}],
      Object.assign(L, {yaxis: {automargin: true, autorange: "reversed"}, xaxis: {ticksuffix: isPct(k) ? " %" : "", rangemode: "tozero", gridcolor: "__GRID__"}}), {displayModeBar: false, responsive: true, locale: "es"});
    document.getElementById("t-trend").innerHTML = table(x.map((g, i) => [g, fmt(k, y[i]), n[i] ? num(n[i]) : ""]), ["Grupo", "Valor", s.n_label || ""]);
    return;
  }
  const valid = y.map((v, i) => [v, i]).filter(p => p[0] !== null);
  const worst = valid.reduce((a, b) => (["red", "amber"].includes(grade(k, b[0])) && (k.direction === "higher_is_better" ? b[0] < a[0] : b[0] > a[0])) ? b : a, valid[0]);
  const firstBad = valid.find(p => grade(k, p[0]) !== "green");
  const cur = grade(k, y[y.length - 1]);
  const title = cur === "green" ? `${who ? "«" + esc(who) + "»: " : ""}en meta en el último periodo (${fmt(k, y[y.length - 1])})`
    : `${who ? "«" + esc(who) + "»: " : ""}fuera de meta${firstBad ? " desde " + x[firstBad[1]] : ""}; el peor periodo fue ${x[worst[1]]} (${fmt(k, worst[0])})`;
  const L = baseLayout(title);
  L.shapes = zones(k, m);
  L.shapes.push({type: "line", xref: "paper", x0: 0, x1: 1, y0: k.target_value * m, y1: k.target_value * m, line: {color: "__INK2__", width: 1}});
  L.annotations.push({xref: "paper", x: 0, y: k.target_value * m, text: "meta", showarrow: false, xanchor: "left", yanchor: "bottom", font: {size: 11}});
  if (firstBad) L.annotations.push({x: x[firstBad[1]], y: y[firstBad[1]] * m, text: "aquí empezó", showarrow: true, arrowhead: 0, ay: -36, font: {size: 11, color: "__INK__"}});
  if (worst && worst !== firstBad && grade(k, worst[0]) !== "green") L.annotations.push({x: x[worst[1]], y: worst[0] * m, text: "peor", showarrow: true, arrowhead: 0, ay: 34, font: {size: 11, color: "__INK__"}});
  L.yaxis = {ticksuffix: axisSuffix(k), gridcolor: "__GRID__", zeroline: false, rangemode: k.direction === "target_range" ? "normal" : "tozero"};
  L.xaxis = {type: "category", showgrid: false, automargin: true};
  Plotly.react("g-trend", [{x, y: y.map(v => v === null ? null : v * m), mode: "lines+markers", line: {color: "__HIGHLIGHT__", width: 2.5},
    marker: {size: 8, color: y.map(v => COLOR[grade(k, v)]), line: {color: "white", width: 1}},
    customdata: x.map((xx, i) => hoverText(k, xx, y[i], n[i], s.n_label)), hovertemplate: "%{customdata}<extra></extra>"}], L, {displayModeBar: false, responsive: true, locale: "es"});
  document.getElementById("t-trend").innerHTML = table(x.map((xx, i) => [xx, fmt(k, y[i]), WORD[grade(k, y[i])], n[i] ? num(n[i]) : ""]), ["Periodo", "Valor", "Semáforo", s.n_label || ""]);
}
function drawBreak(k) {
  const b = k.series.breakdown, share = !!b.share, m = (isPct(k) || share) ? 100 : 1;
  const g = b.groups.slice().sort((a, c) => share ? c.value - a.value : (k.direction === "higher_is_better" ? a.value - c.value : c.value - a.value));
  const fv = v => share ? num(v * 100, 1) + " %" : fmt(k, v);
  const top = g[0];
  const title = share ? `«${esc(top.name)}» concentra ${fv(top.value)} del total` : `El más alejado de la meta: «${esc(top.name)}» con ${fv(top.value)}`;
  const L = baseLayout(title + ` (${esc(b.label)})`);
  L.yaxis = {automargin: true, autorange: "reversed"}; L.xaxis = {ticksuffix: m === 100 ? " %" : "", rangemode: "tozero", gridcolor: "__GRID__"};
  L.margin.t = 60;
  const groupWord = b.label.split(",")[0].replace("por ", "");
  const cd = g.map(r => share ? `${r.name} · ${fv(r.value)} del total · ${num(r.n)} clientes` : hoverText(k, r.name, r.value, r.n, k.series.n_label || "registros"));
  Plotly.react("g-break", [{type: "bar", orientation: "h", x: g.map(r => r.value * m), y: g.map(r => r.name),
    marker: {color: g.map(r => share ? (r.name === "En riesgo" ? "__HIGHLIGHT__" : "__CONTEXT__") : (r.name === state.group ? "__HIGHLIGHT__" : COLOR[grade(k, r.value)]))},
    text: g.map(r => fv(r.value)), textposition: "outside", cliponaxis: false, customdata: cd, hovertemplate: "%{customdata}<extra></extra>"}], L,
    {displayModeBar: false, responsive: true, locale: "es"});
  const gEl = document.getElementById("g-break");
  gEl.removeAllListeners && gEl.removeAllListeners("plotly_click");
  gEl.on("plotly_click", ev => { const name = ev.points[0].y; if (b.trends[name]) { state.group = name; drawTrend(k); drawBreak(k); } });
  document.getElementById("t-break").innerHTML = table(g.map(r => [r.name, fv(r.value), num(r.n)]), [groupWord, "Valor", "Volumen"]);
}

document.addEventListener("click", ev => {
  if (ev.defaultPrevented) return;  // first tap on a touch screen only opens the tooltip
  const bt = ev.target.closest("button");
  if (!bt || bt.id === "ver-todo") return;
  if (bt.classList.contains("alerta")) {  // an alert opens its rubro and its first indicator
    state.rubro = DATA.case_rubros[bt.dataset.case][0]; state.tema = "all"; state.status = "all";
    const c = DATA.valor.casos.find(x => x.caso === bt.dataset.case); if (c) state.kpi = c.componentes[0].kpi;
    if (window.kpiTooltipHide) window.kpiTooltipHide(); render(); document.getElementById("tarjetas").scrollIntoView({behavior: "smooth"}); return;
  }
  if (bt.dataset.status) state.status = bt.dataset.status;
  if (bt.dataset.kpi) { state.kpi = bt.dataset.kpi; state.group = null; }
  if (bt.dataset.status || bt.dataset.kpi) { if (window.kpiTooltipHide) window.kpiTooltipHide(); render(); }
});
document.addEventListener("change", ev => {
  if (ev.target.id === "f-rubro") { state.rubro = ev.target.value; state.group = null; render(); }
  if (ev.target.id === "f-tema") { state.tema = ev.target.value; state.group = null; render(); }
});
window.addEventListener("hashchange", () => { state.rubro = "all"; state.tema = "all"; state.status = "all"; readHash(); render(); });
document.getElementById("tips").innerHTML = DATA.kpis.map(tipHtml).join("");
readHash();
resumen();
render();
</script>
<script src="../assets/js/tooltips.js"></script>
<script src="../assets/js/simulador.js"></script>
</body>
</html>
"""


def build() -> None:
    tables, manifest = load_tables()
    engine = Engine()
    data = payload(tables, engine, manifest)
    page = PAGE
    tokens = {
        "__SURFACE__": theme.SURFACE, "__INK__": theme.INK, "__INK2__": theme.INK_2, "__MUTED__": theme.MUTED,
        "__GRID__": theme.GRID, "__AXIS__": theme.AXIS, "__HIGHLIGHT__": theme.HIGHLIGHT,
        "__CONTEXT_DARK__": theme.CONTEXT_DARK, "__CONTEXT__": theme.CONTEXT, "__GOOD__": theme.STATUS["green"],
        "__WATCH__": theme.STATUS["amber"], "__ACT__": theme.STATUS["red"],
        "__NKPI__": str(len(engine.catalog)), "__DATA_NOTE__": html.escape(data["data_note"]), "__BUILT__": data["built"],
    }  # fmt: skip
    for token, value in tokens.items():
        page = page.replace(token, value)
    page = page.replace("__PAYLOAD__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out = DOCS_DIR / "dashboard" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"  dashboard: {len(data['kpis'])} KPIs -> {out}")
