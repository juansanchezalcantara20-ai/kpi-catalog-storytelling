"""Second presentation layer: an interactive KPI dashboard (one self-contained HTML page, in Spanish).

The story pages explain *why*; the dashboard is the weekly monitoring view: every KPI of
the catalog as a card (value, status, target, trend), filters by topic and status, and a
detail panel with the trend against the target. Card values come from the same
`headline()` as the story pages and the catalog, so the three always agree.
Output: docs/dashboard/index.html (published with the site).
"""

from __future__ import annotations

import html
import json
import math
from typing import Any

import pandas as pd

from .data.pipeline import load_tables
from .engine import Engine, format_threshold, format_value
from .formulas.customers import retention_series
from .paths import DOCS_DIR
from .site.current import headline, mes, trimestre
from .viz import theme

CASES_ES = {
    "service": "Atención de solicitudes",
    "maintenance": "Mantenimiento",
    "inventory": "Inventario",
    "customers": "Clientes",
    "data_quality": "Calidad de los datos",
}


def _month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.to_period("M").dt.start_time


def _complete_months(df: pd.DataFrame, col: str, last_date: pd.Timestamp) -> pd.DataFrame:
    """Drop the last month when the data ends before the month does."""
    if last_date < last_date + pd.offsets.MonthEnd(0):
        return df[df[col] < last_date.to_period("M").start_time]
    return df


def series(
    t: dict[str, pd.DataFrame], e: Engine, cutoff: pd.Timestamp | None = None
) -> dict[str, dict[str, Any]]:
    """One trend (by month) or breakdown (by category) per KPI."""
    out: dict[str, dict[str, Any]] = {}

    def by(kpi: str, df: pd.DataFrame, col: str, label: str, kind: str = "time") -> None:
        r = e.compute_by(kpi, df, col).dropna(subset=["value"])
        x = [mes(d) for d in r[col]] if kind == "time" else [str(v) for v in r[col]]
        out[kpi] = {"kind": kind, "label": label, "x": x, "y": r["value"].tolist()}

    tk = t["tickets"]
    if cutoff is not None:  # months up to the cut-off (the cut-off is the last minute of a month)
        limit = (cutoff + pd.Timedelta(minutes=1)).to_period("M").start_time
        tk = tk[tk["created_month"] < limit]
    res = tk[tk["status"].eq("resolved")]
    by("first_response_time", tk, "created_month", "por mes de apertura")
    for k in ("resolution_time", "sla_compliance", "first_contact_resolution", "reopen_rate"):
        by(k, res, "resolved_month", "por mes de cierre")
    by(
        "backlog_aged_share",
        t["tickets"],
        "queue",
        "solicitudes abiertas a la fecha de corte, por equipo",
        "category",
    )

    ap, wo = t["asset_periods"], t["work_orders"]
    by("mtbf", ap, "month", "por mes")
    by("availability", ap, "month", "por mes")
    by("mttr", wo[wo["wo_type"].eq("corrective")], "month", "por mes")
    pm = wo[wo["wo_type"].eq("preventive")].assign(due_month=lambda d: _month(d["due_date"]))
    by("pm_compliance", pm, "due_month", "por mes programado")
    by("planned_work_share", wo, "month", "por mes")

    daily, ol, fc, snap = (
        t["inventory_daily"],
        t["order_lines"],
        t["forecast"],
        t["inventory_snapshot"],
    )
    end = daily["date"].max()
    ol = _complete_months(ol.assign(m=_month(ol["order_date"])), "m", end)
    by("fill_rate", ol, "m", "por mes del pedido")
    by("otif", ol, "m", "por mes del pedido")
    d = _complete_months(daily.assign(m=_month(daily["date"])), "m", end)
    for k in ("inventory_turnover", "stockout_rate", "days_of_cover"):
        by(k, d, "m", "por mes")
    f = _complete_months(fc.assign(m=_month(fc["week"])), "m", end)
    for k in ("mape", "wape", "forecast_bias"):
        by(k, f, "m", "por mes")
    by(
        "obsolescence_share",
        snap,
        "sku_group",
        "valor del inventario a la última fecha, por grupo de productos",
        "category",
    )

    cs, rfm, sv = t["customer_sales"], t["customer_rfm"], t["survey"]
    ret = retention_series(cs, e.catalog["retention_rate"].params["period"])
    last_q = cs["invoice_date"].max().to_period("Q")
    if cs["invoice_date"].max() < last_q.end_time.normalize():
        ret = ret.drop(index=str(last_q), errors="ignore")
    out["retention_rate"] = {
        "kind": "time",
        "label": "por trimestre",
        "x": [trimestre(q) for q in ret.index],
        "y": ret.tolist(),
    }
    first = cs.groupby("customer_id")["invoice_date"].transform("min").dt.year.astype(str)
    by(
        "repeat_purchase_rate",
        cs.assign(cohorte="Primera compra en " + first),
        "cohorte",
        "por año de primera compra",
        "category",
    )
    seg = rfm.groupby("segment")["monetary"].sum().sort_values(ascending=False)
    out["revenue_at_risk_share"] = {
        "kind": "share",
        "label": "parte del ingreso de 12 meses por tipo de cliente",
        "x": list(seg.index),
        "y": (seg / seg.sum()).tolist(),
        "highlight": "En riesgo",
    }
    by("nps", sv.assign(m=_month(sv["responded_at"])), "m", "por mes de respuesta")

    dq = t["dq_results"]
    for dim in ("completeness", "uniqueness", "validity", "timeliness"):
        sub = dq[dq["dimension"].eq(dim) & (dq["total"] > 0)]
        out[f"dq_{dim}"] = {
            "kind": "category",
            "label": "por conjunto de datos",
            "x": sub["label"].str.replace(r" \(.*\)", "", regex=True).tolist(),
            "y": sub["value"].tolist(),
        }
    return out


def _clean(o: Any) -> Any:
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else round(o, 6)
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def payload(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> dict[str, Any]:
    heads = headline(t, e, manifest)
    snap = (manifest.get("tickets") or {}).get("snapshot")
    sers = series(t, e, pd.Timestamp(snap) if snap else None)
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
        if s["kind"] != "share":
            s = {**s, "status": [e.status(k.id, y) for y in s["y"]]}
        kpis.append(
            {
                "id": k.id,
                "name": k.name,
                "case": k.case,
                "unit": k.unit,
                "direction": k.direction,
                "value": v,
                "display": format_value(k, v) if not math.isnan(v) else "Sin dato",
                "period": h.note or h.period,
                "status": e.status(k.id, v),
                "target": format_threshold(k, with_alert=False),
                "target_full": format_threshold(k),
                "target_value": k.target,
                "green": k.thresholds["green"],
                "question": k.question,
                "meaning": k.meaning,
                "how_to_read": k.how_to_read,
                "misreadings": k.misreadings,
                "owner": k.owner,
                "series": s,
            }
        )
    origins = {manifest[key]["origin"] for key in ("tickets", "process_data", "transactions")}
    return _clean(
        {
            "cases": CASES_ES,
            "kpis": kpis,
            "data_note": "datos públicos reales y simulaciones"
            if "real" in origins
            else "datos simulados: muestran el método, no describen una empresa real",
            "built": manifest["generated_at"][:10],
        }
    )


PAGE = """<!doctype html>
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
body { margin: 0; background: var(--page); color: var(--ink); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { background: #1c5cab; color: #fff; padding: 14px 20px; display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: baseline; }
header h1 { font-size: 19px; margin: 0; font-weight: 650; }
header p { margin: 0; opacity: .9; font-size: 13px; }
header a { color: #fff; margin-left: auto; font-size: 13px; }
main { padding: 16px 20px 32px; max-width: 1400px; margin: 0 auto; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; margin-bottom: 14px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid var(--grid); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 5px 12px; cursor: pointer; font: inherit; font-size: 13px; }
.chip[aria-pressed="true"] { background: var(--ink); color: #fff; border-color: var(--ink); }
.summary { font-size: 13px; color: var(--ink-2); }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); gap: 16px; align-items: start; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }
.card { text-align: left; font: inherit; color: inherit; background: var(--surface); border: 1px solid var(--grid); border-left: 5px solid var(--grid); border-radius: 6px; padding: 9px 11px; cursor: pointer; display: flex; flex-direction: column; gap: 2px; min-height: 140px; }
.card:hover { box-shadow: 0 1px 6px rgba(0,0,0,.08); }
.card[aria-current="true"] { outline: 2px solid var(--accent); outline-offset: 1px; }
.card.green { border-left-color: var(--good); } .card.amber { border-left-color: var(--watch); } .card.red { border-left-color: var(--act); }
.card .case { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; }
.card .name { font-size: 12.5px; color: var(--ink-2); line-height: 1.25; }
.card .value { font-size: 24px; font-weight: 650; line-height: 1.15; }
.card .status, .card .period { font-size: 12px; color: var(--ink-2); }
.card svg { margin-top: auto; }
.detail { background: var(--surface); border: 1px solid var(--grid); border-radius: 6px; padding: 14px 16px; position: sticky; top: 12px; }
.detail h2 { margin: 0 0 2px; font-size: 18px; }
.detail .q { margin: 0 0 8px; color: var(--ink-2); }
.detail .big { font-size: 30px; font-weight: 650; }
.detail .meta { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--ink-2); margin: 2px 0 6px; }
.detail h3 { font-size: 13px; margin: 12px 0 4px; text-transform: uppercase; letter-spacing: .03em; color: var(--ink-2); }
.detail ul { margin: 0; padding-left: 18px; } .detail li { margin: 2px 0; }
.detail .links a { color: var(--accent); margin-right: 14px; font-size: 13px; }
#grafico { width: 100%; height: 330px; }
.nodata { color: var(--ink-2); font-style: italic; }
footer { color: var(--muted); font-size: 12px; margin-top: 18px; }
@media (max-width: 960px) { .layout { grid-template-columns: 1fr; } .detail { position: static; } }
</style>
</head>
<body>
<header>
  <h1>Tablero de indicadores</h1>
  <p>__NKPI__ indicadores · __DATA_NOTE__ · actualizado el __BUILT__</p>
  <a href="../">← Volver a las historias</a>
</header>
<main>
  <div class="toolbar">
    <div class="chips" id="temas" role="group" aria-label="Tema"></div>
    <div class="chips" id="estados" role="group" aria-label="Semáforo"></div>
    <span class="summary" id="resumen" aria-live="polite"></span>
  </div>
  <div class="layout">
    <section class="grid" id="tarjetas" aria-label="Tarjetas de indicadores"></section>
    <section class="detail" id="detalle" aria-live="polite"></section>
  </div>
  <footer>Semáforo: 🟢 En meta · 🟡 Vigilar · 🔴 Actuar, siempre frente a la meta del catálogo y nunca frente a un promedio.
  Cada tarjeta muestra el mismo valor que su historia y su ficha del catálogo. Las tendencias usan solo periodos completos. Las metas son ilustrativas.</footer>
</main>
<script>
const DATA = __PAYLOAD__;
const ICON = {green: "🟢", amber: "🟡", red: "🔴", "n/a": "⚪"};
const WORD = {green: "En meta", amber: "Vigilar", red: "Actuar", "n/a": "Sin dato"};
const COLOR = {green: "__GOOD__", amber: "__WATCH__", red: "__ACT__", "n/a": "__CONTEXT__"};
const state = {caseId: "all", status: "all", kpi: null};

function isPct(k, kind) { return k.unit === "percent" || kind === "share"; }
function k100(k, kind) { return isPct(k, kind) ? 100 : 1; }
function suffix(k, kind) { return isPct(k, kind) ? " %" : ({hours: " h", days: " días", times_per_year: ""}[k.unit] || ""); }
function fmt(k, v, kind) {
  if (v === null || v === undefined) return "sin dato";
  if (k.unit === "score" && kind !== "share") return (v >= 0 ? "+" : "") + v.toFixed(0);
  return (v * k100(k, kind)).toFixed(1) + suffix(k, kind);
}

function sparkline(k) {
  const s = k.series;
  if (!s || s.kind !== "time" || s.y.length < 2) return "";
  const ys = s.y.filter(v => v !== null), w = 180, h = 30;
  const lo = Math.min(...ys), hi = Math.max(...ys), span = (hi - lo) || 1;
  const pts = s.y.map((v, i) => v === null ? null : [i / (s.y.length - 1) * w, h - 3 - (v - lo) / span * (h - 6)]).filter(Boolean);
  const last = pts[pts.length - 1];
  return `<svg width="${w}" height="${h}" role="img" aria-label="tendencia"><polyline fill="none" stroke="__CONTEXT_DARK__" stroke-width="1.5" points="${pts.map(p => p.join(",")).join(" ")}"/><circle cx="${last[0]}" cy="${last[1]}" r="3" fill="__HIGHLIGHT__"/></svg>`;
}

function chips() {
  const temas = [["all", "Todos los temas"], ...Object.entries(DATA.cases)];
  document.getElementById("temas").innerHTML = temas.map(([id, t]) =>
    `<button class="chip" aria-pressed="${state.caseId === id}" data-case="${id}">${t}</button>`).join("");
  const sts = [["all", "Cualquier estado"], ["red", "🔴 Actuar"], ["amber", "🟡 Vigilar"], ["green", "🟢 En meta"]];
  document.getElementById("estados").innerHTML = sts.map(([id, t]) =>
    `<button class="chip" aria-pressed="${state.status === id}" data-status="${id}">${t}</button>`).join("");
}

function visible() {
  return DATA.kpis.filter(k => (state.caseId === "all" || k.case === state.caseId) && (state.status === "all" || k.status === state.status));
}

function render() {
  chips();
  const list = visible();
  if (!list.find(k => k.id === state.kpi)) state.kpi = list.length ? list[0].id : null;
  document.getElementById("tarjetas").innerHTML = list.map(k => `
    <button class="card ${k.status.replace("/", "")}" data-kpi="${k.id}" aria-current="${k.id === state.kpi}">
      <span class="case">${DATA.cases[k.case]}</span>
      <span class="name">${k.name}</span>
      <span class="value">${k.display}</span>
      <span class="status">${ICON[k.status]} ${WORD[k.status]} · meta ${k.target}</span>
      <span class="period">${k.period}</span>
      ${sparkline(k)}
    </button>`).join("") || "<p>Ningún indicador cumple estos filtros.</p>";
  const c = {red: 0, amber: 0, green: 0};
  list.forEach(k => { if (k.status in c) c[k.status]++; });
  document.getElementById("resumen").textContent = `${list.length} indicadores · ${c.red} para actuar · ${c.amber} para vigilar · ${c.green} en meta`;
  detail();
  try { history.replaceState(null, "", "#" + [state.caseId, state.status, state.kpi || ""].join("/")); } catch (e) {}
}

function detail() {
  const el = document.getElementById("detalle");
  const k = DATA.kpis.find(x => x.id === state.kpi);
  if (!k) { el.innerHTML = ""; return; }
  el.innerHTML = `
    <h2>${k.name}</h2>
    <p class="q">${k.question}</p>
    <div class="big">${ICON[k.status]} ${k.display}</div>
    <div class="meta"><span>${WORD[k.status]}</span><span>${k.period}</span><span>Meta ${k.target_full}</span><span>Responsable: ${k.owner}</span></div>
    <p>${k.meaning}</p>
    ${k.series.kind === "none" ? `<p class="nodata">Sin gráfico: ${k.series.label}.</p>` : `<div id="grafico" role="img" aria-label="${k.name}, ${k.series.label}"></div>`}
    <h3>Cómo leerlo</h3><p>${k.how_to_read}</p>
    <h3>Errores comunes al leerlo</h3><ul>${k.misreadings.map(m => `<li>${m}</li>`).join("")}</ul>
    <p class="links"><a href="../cases/${k.case}/">Ver la historia →</a><a href="../catalog/${k.id}/">Ficha completa del indicador →</a></p>`;
  if (k.series.kind !== "none") drawChart(k);
}

function drawChart(k) {
  const s = k.series, m = k100(k, s.kind), suf = suffix(k, s.kind);
  const dec = isPct(k, s.kind) ? 0 : 1;
  const layout = {
    margin: {l: 56, r: 16, t: 34, b: 44}, paper_bgcolor: "__SURFACE__", plot_bgcolor: "__SURFACE__",
    font: {family: "system-ui, -apple-system, Segoe UI, sans-serif", size: 12, color: "__INK2__"}, separators: ". ",
    title: {text: s.label.replace(/^./, c => c.toUpperCase()), x: 0, font: {size: 13, color: "__INK2__"}},
    showlegend: false, shapes: [], annotations: []};
  const yv = s.y.map(v => v === null ? null : v * m);
  let traces;
  if (s.kind === "time") {
    traces = [{x: s.x, y: yv, mode: "lines+markers", line: {color: "__HIGHLIGHT__", width: 2.5}, marker: {size: 6, color: s.status.map(st => COLOR[st])},
      hovertemplate: "%{x}: %{y:." + (dec + 1) + "f}" + suf + "<extra></extra>"}];
    layout.yaxis = {ticksuffix: suf, tickformat: "." + dec + "f", gridcolor: "__GRID__", zeroline: false, rangemode: k.direction === "target_range" ? "normal" : "tozero"};
    layout.xaxis = {showgrid: false, linecolor: "__AXIS__", automargin: true, type: "category"};
  } else {
    const colors = s.kind === "share" ? s.x.map(x => x === s.highlight ? "__HIGHLIGHT__" : "__CONTEXT__") : s.status.map(st => COLOR[st]);
    traces = [{type: "bar", x: yv, y: s.x, orientation: "h", marker: {color: colors},
      text: s.y.map(v => fmt(k, v, s.kind)), textposition: "outside", cliponaxis: false,
      hovertemplate: "%{y}: %{x:." + (dec + 1) + "f}" + suf + "<extra></extra>"}];
    layout.yaxis = {automargin: true, autorange: "reversed", showgrid: false};
    layout.xaxis = {ticksuffix: suf, tickformat: "." + dec + "f", gridcolor: "__GRID__", rangemode: "tozero", zeroline: false};
  }
  if (s.kind !== "share") {
    const axis = s.kind === "time" ? "y" : "x";
    const kk = isPct(k, s.kind) ? 100 : 1;
    if (k.direction === "target_range") {
      const band = {type: "rect", layer: "below", fillcolor: "rgba(12,163,12,0.10)", line: {width: 0}};
      if (axis === "y") Object.assign(band, {xref: "paper", x0: 0, x1: 1, y0: k.green[0] * kk, y1: k.green[1] * kk});
      else Object.assign(band, {yref: "paper", y0: 0, y1: 1, x0: k.green[0] * kk, x1: k.green[1] * kk});
      layout.shapes.push(band);
    }
    const tv = k.target_value * kk;
    const line = {type: "line", line: {color: "__INK2__", width: 1}};
    if (axis === "y") Object.assign(line, {xref: "paper", x0: 0, x1: 1, y0: tv, y1: tv});
    else Object.assign(line, {yref: "paper", y0: 0, y1: 1, x0: tv, x1: tv});
    layout.shapes.push(line);
    layout.annotations.push(axis === "y"
      ? {xref: "paper", x: 0, y: tv, text: "meta", showarrow: false, xanchor: "left", yanchor: "bottom", font: {size: 11, color: "__INK2__"}}
      : {yref: "paper", y: 1, x: tv, text: "meta", showarrow: false, yanchor: "bottom", font: {size: 11, color: "__INK2__"}});
  }
  Plotly.react("grafico", traces, layout, {displayModeBar: false, responsive: true, locale: "es"});
}

document.addEventListener("click", ev => {
  const b = ev.target.closest("button");
  if (!b) return;
  if (b.dataset.case) state.caseId = b.dataset.case;
  if (b.dataset.status) state.status = b.dataset.status;
  if (b.dataset.kpi) state.kpi = b.dataset.kpi;
  render();
});
const parts = decodeURIComponent(location.hash.slice(1)).split("/");
if (parts[0] && (parts[0] === "all" || parts[0] in DATA.cases)) state.caseId = parts[0];
if (["all", "red", "amber", "green"].includes(parts[1])) state.status = parts[1];
if (parts[2]) state.kpi = parts[2];
render();
</script>
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
