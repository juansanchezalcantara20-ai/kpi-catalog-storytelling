"""Second presentation layer: an interactive KPI dashboard (one self-contained HTML page).

The story site explains *why*; the dashboard is the monitoring view a manager opens every
week: every KPI of the catalog as a card (value, status, target, trend), filters by domain
and status, and a detail panel with the trend against the target and how to read it.
Values come from the same engine as the site; definitions, targets and texts come from
the catalog. Output: docs/dashboard/index.html (published with the site).
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
from .site.current import current_values
from .viz import theme


def _month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.to_period("M").dt.start_time


def _complete_months(df: pd.DataFrame, col: str, last_date: pd.Timestamp) -> pd.DataFrame:
    """Drop the last month when the data ends before the month does."""
    if last_date < last_date + pd.offsets.MonthEnd(0):
        return df[df[col] < last_date.to_period("M").start_time]
    return df


def series(t: dict[str, pd.DataFrame], e: Engine) -> dict[str, dict[str, Any]]:
    """One trend (by month) or breakdown (by category) per KPI."""
    out: dict[str, dict[str, Any]] = {}

    def by(kpi: str, df: pd.DataFrame, col: str, label: str, kind: str = "time") -> None:
        r = e.compute_by(kpi, df, col).dropna(subset=["value"])
        x = [d.strftime("%Y-%m") for d in r[col]] if kind == "time" else [str(v) for v in r[col]]
        out[kpi] = {"kind": kind, "label": label, "x": x, "y": r["value"].tolist()}

    tk = t["tickets"]
    res = tk[tk["status"].eq("resolved")]
    by("first_response_time", tk, "created_month", "by month of creation")
    for k in ("resolution_time", "sla_compliance", "first_contact_resolution", "reopen_rate"):
        by(k, res, "resolved_month", "by month of resolution")
    by("backlog_aged_share", tk, "queue", "open tickets at year end, by queue", "category")

    ap, wo = t["asset_periods"], t["work_orders"]
    by("mtbf", ap, "month", "by month")
    by("availability", ap, "month", "by month")
    by("mttr", wo[wo["wo_type"].eq("corrective")], "month", "by month")
    pm = wo[wo["wo_type"].eq("preventive")].assign(due_month=lambda d: _month(d["due_date"]))
    by("pm_compliance", pm, "due_month", "by month the PM was due")
    by("planned_work_share", wo, "month", "by month")

    daily, ol, fc, snap = (
        t["inventory_daily"],
        t["order_lines"],
        t["forecast"],
        t["inventory_snapshot"],
    )
    end = daily["date"].max()
    ol = _complete_months(ol.assign(m=_month(ol["order_date"])), "m", end)
    by("fill_rate", ol, "m", "by month of order")
    by("otif", ol, "m", "by month of order")
    d = _complete_months(daily.assign(m=_month(daily["date"])), "m", end)
    for k in ("inventory_turnover", "stockout_rate", "days_of_cover"):
        by(k, d, "m", "by month")
    f = _complete_months(fc.assign(m=_month(fc["week"])), "m", end)
    for k in ("mape", "wape", "forecast_bias"):
        by(k, f, "m", "by month")
    by(
        "obsolescence_share",
        snap,
        "sku_group",
        "stock value at the last date, by SKU group",
        "category",
    )

    cs, rfm, sv = t["customer_sales"], t["customer_rfm"], t["survey"]
    ret = retention_series(cs, e.catalog["retention_rate"].params["period"])
    last_q = cs["invoice_date"].max().to_period("Q")
    if cs["invoice_date"].max() < last_q.end_time.normalize():
        ret = ret.drop(index=str(last_q), errors="ignore")
    out["retention_rate"] = {
        "kind": "time",
        "label": "by quarter",
        "x": list(ret.index),
        "y": ret.tolist(),
    }
    first = cs.groupby("customer_id")["invoice_date"].transform("min").dt.year.astype(str)
    by(
        "repeat_purchase_rate",
        cs.assign(cohort="Cohort " + first),
        "cohort",
        "by year of first purchase",
        "category",
    )
    seg = rfm.groupby("segment")["monetary"].sum().sort_values(ascending=False)
    out["revenue_at_risk_share"] = {
        "kind": "share",
        "label": "share of 12-month revenue by RFM segment",
        "x": list(seg.index),
        "y": (seg / seg.sum()).tolist(),
        "highlight": "At risk",
    }
    by("nps", sv.assign(m=_month(sv["responded_at"])), "m", "by month of response")

    dq = t["dq_results"]
    for dim in ("completeness", "uniqueness", "validity", "timeliness"):
        sub = dq[dq["dimension"].eq(dim) & (dq["total"] > 0)]
        out[f"dq_{dim}"] = {
            "kind": "category",
            "label": "by landing dataset",
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
    cur = current_values(t, e)
    sers = series(t, e)
    kpis = []
    for k in e.catalog:
        v = cur.get(k.id, float("nan"))
        s = sers.get(k.id, {"kind": "none", "x": [], "y": []})
        s = (
            {**s, "status": [e.status(k.id, y) if y is not None else "n/a" for y in s["y"]]}
            if s["kind"] != "share"
            else s
        )
        kpis.append(
            {
                "id": k.id,
                "name": k.name,
                "case": k.case,
                "unit": k.unit,
                "direction": k.direction,
                "value": v,
                "display": format_value(k, v),
                "status": e.status(k.id, v),
                "target": format_threshold(k).split(" (")[0],
                "target_full": format_threshold(k),
                "target_value": k.target,
                "green": k.thresholds["green"],
                "amber": k.thresholds["amber"],
                "question": k.question,
                "how_to_read": k.how_to_read,
                "misreadings": k.misreadings,
                "owner": k.owner,
                "series": s,
            }
        )
    origins = {manifest[key]["origin"] for key in ("process_data", "transactions")}
    return _clean(
        {
            "cases": {c: m["title"] for c, m in e.catalog.cases.items()},
            "kpis": kpis,
            "data_note": "public UCI data + simulations"
            if "real" in origins
            else "synthetic data (seeded generators)",
            "built": manifest["generated_at"][:10],
        }
    )


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KPI Dashboard</title>
<script src="../assets/js/plotly.min.js"></script>
<style>
:root {
  --surface: __SURFACE__; --page: #f4f4f1; --ink: __INK__; --ink-2: __INK2__; --muted: __MUTED__;
  --grid: __GRID__; --accent: __HIGHLIGHT__; --good: __GOOD__; --watch: __WATCH__; --act: __ACT__;
  --good-ink: #006300; --watch-ink: #8a5a00; --act-ink: #b42323;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { background: #1c5cab; color: #fff; padding: 14px 20px; display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: baseline; }
header h1 { font-size: 19px; margin: 0; font-weight: 650; }
header p { margin: 0; opacity: .85; font-size: 13px; }
header a { color: #fff; margin-left: auto; font-size: 13px; }
main { padding: 16px 20px 32px; max-width: 1400px; margin: 0 auto; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; margin-bottom: 14px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid var(--grid); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 5px 12px; cursor: pointer; font: inherit; font-size: 13px; }
.chip[aria-pressed="true"] { background: var(--ink); color: #fff; border-color: var(--ink); }
.summary { font-size: 13px; color: var(--ink-2); }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); gap: 16px; align-items: start; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.card { text-align: left; font: inherit; color: inherit; background: var(--surface); border: 1px solid var(--grid); border-left: 5px solid var(--grid); border-radius: 6px; padding: 9px 11px; cursor: pointer; display: flex; flex-direction: column; gap: 2px; min-height: 128px; }
.card:hover { box-shadow: 0 1px 6px rgba(0,0,0,.08); }
.card[aria-current="true"] { outline: 2px solid var(--accent); outline-offset: 1px; }
.card.green { border-left-color: var(--good); } .card.amber { border-left-color: var(--watch); } .card.red { border-left-color: var(--act); }
.card .case { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; }
.card .name { font-size: 12.5px; color: var(--ink-2); line-height: 1.25; }
.card .value { font-size: 24px; font-weight: 650; line-height: 1.15; }
.card .status { font-size: 12px; color: var(--ink-2); }
.icon { font-weight: 700; }
.green .icon, .st-green { color: var(--good-ink); } .amber .icon, .st-amber { color: var(--watch-ink); } .red .icon, .st-red { color: var(--act-ink); }
.card svg { margin-top: auto; }
.detail { background: var(--surface); border: 1px solid var(--grid); border-radius: 6px; padding: 14px 16px; position: sticky; top: 12px; }
.detail h2 { margin: 0 0 2px; font-size: 18px; }
.detail .q { margin: 0 0 8px; color: var(--ink-2); }
.detail .big { font-size: 30px; font-weight: 650; }
.detail .meta { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--ink-2); margin: 2px 0 6px; }
.detail h3 { font-size: 13px; margin: 12px 0 4px; text-transform: uppercase; letter-spacing: .03em; color: var(--ink-2); }
.detail ul { margin: 0; padding-left: 18px; } .detail li { margin: 2px 0; }
.detail .links a { color: var(--accent); margin-right: 14px; font-size: 13px; }
#chart { width: 100%; height: 330px; }
footer { color: var(--muted); font-size: 12px; margin-top: 18px; }
@media (max-width: 960px) { .layout { grid-template-columns: 1fr; } .detail { position: static; } }
</style>
</head>
<body>
<header>
  <h1>KPI Dashboard</h1>
  <p>__NKPI__ KPIs · one catalog, one engine · __DATA_NOTE__ · built __BUILT__</p>
  <a href="../">← Story site</a>
</header>
<main>
  <div class="toolbar">
    <div class="chips" id="cases" role="group" aria-label="Domain"></div>
    <div class="chips" id="statuses" role="group" aria-label="Status"></div>
    <span class="summary" id="summary" aria-live="polite"></span>
  </div>
  <div class="layout">
    <section class="grid" id="grid" aria-label="KPI cards"></section>
    <section class="detail" id="detail" aria-live="polite"></section>
  </div>
  <footer>Status: ✓ on target · ! watch · ✕ act - always against the catalog target, never against an average.
  Values cover each case's full period; trends drop incomplete last periods. Targets are illustrative.</footer>
</main>
<script>
const DATA = __PAYLOAD__;
const ICON = {green: "✓", amber: "!", red: "✕", "n/a": "–"};
const WORD = {green: "On target", amber: "Watch", red: "Act", "n/a": "No data"};
const COLOR = {green: "__GOOD__", amber: "__WATCH__", red: "__ACT__", "n/a": "__CONTEXT__"};
const state = {caseId: "all", status: "all", kpi: null};

function fmt(k, v) {
  if (v === null || v === undefined) return "n/a";
  if (k.unit === "percent") return (v * 100).toFixed(1) + "%";
  if (k.unit === "score") return (v >= 0 ? "+" : "") + v.toFixed(0);
  const suffix = {hours: " h", days: " d", times_per_year: "x"}[k.unit] || "";
  return v.toFixed(1) + suffix;
}
function axisFormat(k) { return k.unit === "percent" ? ".0%" : (k.unit === "score" ? "+.0f" : ".1f"); }

function sparkline(k) {
  const s = k.series;
  if (!s || s.kind !== "time" || s.y.length < 2) return "";
  const ys = s.y.filter(v => v !== null), w = 170, h = 30;
  const lo = Math.min(...ys), hi = Math.max(...ys), span = (hi - lo) || 1;
  const pts = s.y.map((v, i) => v === null ? null : [i / (s.y.length - 1) * w, h - 3 - (v - lo) / span * (h - 6)]).filter(Boolean);
  const last = pts[pts.length - 1];
  return `<svg width="${w}" height="${h}" role="img" aria-label="trend"><polyline fill="none" stroke="__CONTEXT_DARK__" stroke-width="1.5" points="${pts.map(p => p.join(",")).join(" ")}"/><circle cx="${last[0]}" cy="${last[1]}" r="3" fill="__HIGHLIGHT__"/></svg>`;
}

function chips() {
  const cases = [["all", "All domains"], ...Object.entries(DATA.cases)];
  document.getElementById("cases").innerHTML = cases.map(([id, t]) =>
    `<button class="chip" aria-pressed="${state.caseId === id}" data-case="${id}">${t}</button>`).join("");
  const sts = [["all", "Any status"], ["red", "✕ Act"], ["amber", "! Watch"], ["green", "✓ On target"]];
  document.getElementById("statuses").innerHTML = sts.map(([id, t]) =>
    `<button class="chip" aria-pressed="${state.status === id}" data-status="${id}">${t}</button>`).join("");
}

function visible() {
  return DATA.kpis.filter(k => (state.caseId === "all" || k.case === state.caseId) && (state.status === "all" || k.status === state.status));
}

function render() {
  chips();
  const list = visible();
  if (!list.find(k => k.id === state.kpi)) state.kpi = list.length ? list[0].id : null;
  document.getElementById("grid").innerHTML = list.map(k => `
    <button class="card ${k.status.replace("/", "")}" data-kpi="${k.id}" aria-current="${k.id === state.kpi}">
      <span class="case">${DATA.cases[k.case]}</span>
      <span class="name">${k.name}</span>
      <span class="value">${k.display}</span>
      <span class="status"><span class="icon">${ICON[k.status]}</span> ${WORD[k.status]} · target ${k.target}</span>
      ${sparkline(k)}
    </button>`).join("") || "<p>No KPI matches these filters.</p>";
  const counts = {red: 0, amber: 0, green: 0};
  list.forEach(k => { if (k.status in counts) counts[k.status]++; });
  document.getElementById("summary").textContent = `${list.length} KPIs · ${counts.red} act · ${counts.amber} watch · ${counts.green} on target`;
  detail();
  try { history.replaceState(null, "", "#" + [state.caseId, state.status, state.kpi || ""].join("/")); } catch (e) {}
}

function detail() {
  const el = document.getElementById("detail");
  const k = DATA.kpis.find(x => x.id === state.kpi);
  if (!k) { el.innerHTML = ""; return; }
  el.innerHTML = `
    <h2>${k.name}</h2>
    <p class="q">${k.question}</p>
    <div class="big"><span class="st-${k.status.replace("/", "")}">${ICON[k.status]}</span> ${k.display}</div>
    <div class="meta"><span>${WORD[k.status]}</span><span>Target ${k.target_full}</span><span>Owner: ${k.owner}</span></div>
    <div id="chart" role="img" aria-label="${k.name} ${k.series.label || ""}"></div>
    <h3>How to read it</h3><p>${k.how_to_read}</p>
    <h3>Common misreadings</h3><ul>${k.misreadings.map(m => `<li>${m}</li>`).join("")}</ul>
    <p class="links"><a href="../cases/${k.case}/">Open the story →</a><a href="../catalog/${k.id}/">Definition, formula, SQL, worked example →</a></p>`;
  drawChart(k);
}

function drawChart(k) {
  const s = k.series, layout = {
    margin: {l: 52, r: 16, t: 34, b: 44}, paper_bgcolor: "__SURFACE__", plot_bgcolor: "__SURFACE__",
    font: {family: "system-ui, -apple-system, Segoe UI, sans-serif", size: 12, color: "__INK2__"},
    title: {text: (s.label || "").replace(/^./, c => c.toUpperCase()), x: 0, font: {size: 13, color: "__INK2__"}},
    yaxis: {tickformat: axisFormat(k), gridcolor: "__GRID__", zeroline: false, rangemode: k.direction === "target_range" ? "normal" : "tozero"},
    xaxis: {showgrid: false, linecolor: "__AXIS__", automargin: true}, showlegend: false, shapes: [], annotations: []};
  let traces;
  if (s.kind === "time") {
    traces = [{x: s.x, y: s.y, mode: "lines+markers", line: {color: "__HIGHLIGHT__", width: 2.5}, marker: {size: 6, color: s.status.map(st => COLOR[st])},
      hovertemplate: "%{x}: %{y:" + axisFormat(k) + "}<extra></extra>"}];
  } else {
    const colors = s.kind === "share" ? s.x.map(x => x === s.highlight ? "__HIGHLIGHT__" : "__CONTEXT__") : s.status.map(st => COLOR[st]);
    traces = [{type: "bar", x: s.y, y: s.x, orientation: "h", marker: {color: colors},
      text: s.y.map(v => fmt(k.unit === "score" && s.kind === "share" ? {unit: "percent"} : (s.kind === "share" ? {unit: "percent"} : k), v)), textposition: "outside", cliponaxis: false,
      hovertemplate: "%{y}: %{x:" + (s.kind === "share" ? ".1%" : axisFormat(k)) + "}<extra></extra>"}];
    layout.yaxis = {automargin: true, autorange: "reversed", showgrid: false};
    layout.xaxis = {tickformat: s.kind === "share" ? ".0%" : axisFormat(k), gridcolor: "__GRID__", rangemode: "tozero", zeroline: false};
  }
  if (s.kind !== "share") {
    const axis = s.kind === "time" ? "y" : "x";
    if (k.direction === "target_range") {
      const band = {type: "rect", layer: "below", fillcolor: "rgba(12,163,12,0.10)", line: {width: 0}};
      if (axis === "y") Object.assign(band, {xref: "paper", x0: 0, x1: 1, y0: k.green[0], y1: k.green[1]});
      else Object.assign(band, {yref: "paper", y0: 0, y1: 1, x0: k.green[0], x1: k.green[1]});
      layout.shapes.push(band);
    }
    const line = {type: "line", line: {color: "__INK2__", width: 1}};
    if (axis === "y") Object.assign(line, {xref: "paper", x0: 0, x1: 1, y0: k.target_value, y1: k.target_value});
    else Object.assign(line, {yref: "paper", y0: 0, y1: 1, x0: k.target_value, x1: k.target_value});
    layout.shapes.push(line);
    layout.annotations.push(axis === "y"
      ? {xref: "paper", x: 0, y: k.target_value, text: "target", showarrow: false, xanchor: "left", yanchor: "bottom", font: {size: 11, color: "__INK2__"}}
      : {yref: "paper", y: 1, x: k.target_value, text: "target", showarrow: false, yanchor: "bottom", font: {size: 11, color: "__INK2__"}});
  }
  Plotly.react("chart", traces, layout, {displayModeBar: false, responsive: true});
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
