"""The two axes of the site: one page per rubro (sector), one per tema (theme), and the rubro × tema matrix."""

from __future__ import annotations

import html
import math

from ..catalog import rubros_config
from ..engine import Engine, format_threshold, format_value
from ..valor import money
from ..viz import theme
from .common import tiles
from .current import Headline
from .plantilla import con_datos_reales, tipo_resultado

MAX_TILES = 8
ETIQUETA = {
    "observado": "🟢 Resultado observado en datos reales",
    "estimado": "🔵 Resultado estimado (escenario)",
}


def _titulo(engine: Engine, case: str) -> str:
    return engine.catalog.cases[case]["title"]


def rubro_kpis(engine: Engine, rubro: str) -> list[str]:
    """KPIs of a rubro for its mini-dashboard: those of its own cases first, then the shared ones (at most 8)."""
    own = set(engine.catalog.cases_for_rubro(rubro))
    ks = engine.catalog.for_rubro(rubro)
    ks = sorted(ks, key=lambda k: (k.case not in own, list(engine.catalog.cases).index(k.case)))
    return [k.id for k in ks][:MAX_TILES]


def resumen_casos(engine: Engine, manifest: dict) -> dict[str, dict]:
    return {
        c: {"tipo": tipo_resultado(c, manifest), "reales": con_datos_reales(c, manifest)}
        for c in engine.catalog.cases
    }


def contador(engine: Engine, manifest: dict) -> str:
    info = resumen_casos(engine, manifest)
    obs = sum(v["tipo"] == "observado" for v in info.values())
    est = len(info) - obs
    reales = sum(v["reales"] for v in info.values())
    return (
        f'<p class="contador" markdown="0" data-observados="{obs}" data-estimados="{est}" data-reales="{reales}">'
        f"<b>{obs} casos con resultado observado en datos reales</b> · {est} con resultado estimado (escenario) · "
        f"{reales} de {len(info)} casos usan datos públicos reales; el resto, datos simulados o de referencia, y lo dicen.</p>\n\n"
    )


def _caso_item(engine: Engine, case: str, manifest: dict, up: str) -> str:
    tipo = tipo_resultado(case, manifest)
    datos = (
        "datos reales" if con_datos_reales(case, manifest) else "datos simulados o de referencia"
    )
    return f"- [{_titulo(engine, case)}]({up}cases/{case}.md) · {ETIQUETA[tipo]} · {datos}"


# ------------------------------------------------------------------ rubros
def rubro_page(engine: Engine, values: dict[str, Headline], manifest: dict, rubro: str) -> str:
    cfg = rubros_config()
    r = cfg["rubros"][rubro]
    md = [f"# {r['nombre']}\n"]
    md.append("## Cómo gana dinero este rubro\n")
    md += [f"- {line}" for line in r["como_gana"]]
    md.append("\n## Los indicadores que mira\n")
    md.append(tiles(engine, values, rubro_kpis(engine, rubro)))
    metas = [
        (k, k.metas_por_rubro[rubro])
        for k in engine.catalog.for_rubro(rubro)
        if rubro in k.metas_por_rubro
    ]
    if metas:
        md.append(
            "**Metas de referencia para este rubro** (distintas de la meta general del catálogo):\n"
        )
        md.append("| Indicador | Meta general | Meta en este rubro | Por qué |")
        md.append("|---|---|---|---|")
        sign = {"higher_is_better": "≥", "lower_is_better": "≤"}
        for k, m in metas:
            md.append(f"| [{k.name}](../catalog/{k.id}.md) | {format_threshold(k, with_alert=False)} | "
                      f"{sign.get(k.direction, '')} {format_value(k, m['target'])} | {m['why']} |")  # fmt: skip
        md.append("")
    md.append("## Casos\n")
    md += [_caso_item(engine, c, manifest, "../") for c in engine.catalog.cases_for_rubro(rubro)]
    md.append("\n## Dos errores comunes al medir en este rubro\n")
    for i, e in enumerate(r["errores"], start=1):
        md.append(f"{i}. **{e['error']}** {e['mejor']}")
    md.append(
        f"\n[Ver en el tablero](../dashboard/index.html#/rubro/{rubro}){{ .md-button .md-button--primary }} "
        "[Todos los rubros](index.md){ .md-button }\n"
    )
    md.append(
        f'<div class="rubro-meta" markdown="0" data-rubro="{rubro}" data-kpis="{len(rubro_kpis(engine, rubro))}"></div>\n'
    )
    return "\n".join(md)


def rubros_index(engine: Engine, manifest: dict) -> str:
    cfg = rubros_config()
    md = [
        "# Por rubro\n",
        "Cada rubro gana dinero de una forma distinta, y por eso mira indicadores distintos. Los rubros se presentan como sectores de "
        "la economía: los casos comparan grupos (países, regiones, tipos de entidad), nunca empresas con nombre.\n",
        contador(engine, manifest),
        "| Rubro | Cómo gana dinero | Casos | Indicadores |",
        "|---|---|---|---|",
    ]
    for rid, r in cfg["rubros"].items():
        casos = ", ".join(
            f"[{_titulo(engine, c)}](../cases/{c}.md)" for c in engine.catalog.cases_for_rubro(rid)
        )
        md.append(
            f"| [{r['nombre']}]({rid}.md) | {r['como_gana'][0]} | {casos} | {len(engine.catalog.for_rubro(rid))} |"
        )
    return "\n".join(md) + "\n"


# ------------------------------------------------------------------ temas
def tema_page(engine: Engine, values: dict[str, Headline], manifest: dict, tema: str) -> str:
    cfg = rubros_config()
    t = cfg["temas"][tema]
    md = [f"# {t['nombre']}\n", f'<p class="story-question">{html.escape(t["pregunta"])}</p>\n']
    ks = engine.catalog.for_tema(tema)
    md.append(f"## Indicadores de este tema ({len(ks)})\n")
    md.append("| Indicador | Qué responde | Rubros | Meta | Valor de referencia |")
    md.append("|---|---|---|---|---|")
    for k in ks:
        h = values.get(k.id)
        if h is None or math.isnan(h.value):
            val = "⚪ Sin dato"
        else:
            st = engine.status(k.id, h.value)
            val = f"{theme.STATUS_ICON[st]} {format_value(k, h.value)} · {h.period}"
        rub = ", ".join(f"[{cfg['rubros'][r]['nombre']}](../rubros/{r}.md)" for r in k.rubros)
        md.append(
            f"| [{k.name}](../catalog/{k.id}.md) | {k.question} | {rub} | {format_threshold(k, with_alert=False)} | {val} |"
        )
    casos = [c for c, d in engine.catalog.cases.items() if d["tema"] == tema]
    md.append("\n## Casos de este tema\n")
    md += [_caso_item(engine, c, manifest, "../") for c in casos] or [
        "- Todavía no hay un caso cuyo tema principal sea este."
    ]
    md.append(
        f"\n[Ver en el tablero](../dashboard/index.html#/tema/{tema}){{ .md-button .md-button--primary }} [Todos los temas](index.md){{ .md-button }}\n"
    )
    return "\n".join(md)


def temas_index(engine: Engine) -> str:
    cfg = rubros_config()
    md = ["# Por tema\n", "El mismo tipo de problema aparece en rubros muy distintos. Cada tema reúne los indicadores que lo miden.\n",
          "| Tema | La pregunta | Indicadores | Casos |", "|---|---|---|---|"]  # fmt: skip
    for tid, t in cfg["temas"].items():
        n_casos = sum(d["tema"] == tid for d in engine.catalog.cases.values())
        md.append(
            f"| [{t['nombre']}]({tid}.md) | {t['pregunta']} | {len(engine.catalog.for_tema(tid))} | {n_casos} |"
        )
    return "\n".join(md) + "\n"


# ------------------------------------------------------------------ matriz
def matriz(engine: Engine, manifest: dict) -> str:
    """Rubro × tema: a case link, or the number of KPIs (to the filtered dashboard), or «pendiente»."""
    cfg = rubros_config()
    temas = list(cfg["temas"])
    head = "".join(
        f'<th scope="col"><a href="temas/{t}/">{html.escape(cfg["temas"][t]["nombre"])}</a></th>'
        for t in temas
    )
    rows = []
    for rid, r in cfg["rubros"].items():
        cells = []
        for t in temas:
            casos = [
                c
                for c in engine.catalog.cases_for_rubro(rid)
                if engine.catalog.cases[c]["tema"] == t
            ]
            n = sum(1 for k in engine.catalog.for_rubro(rid) if k.tema == t)
            if casos:
                links = "<br>".join(
                    f'<a href="cases/{c}/">{"🟢" if tipo_resultado(c, manifest) == "observado" else "🔵"} {html.escape(_titulo(engine, c))}</a>'
                    for c in casos
                )
                cells.append(f'<td class="celda-caso">{links}</td>')
            elif n:
                cells.append(
                    f'<td><a href="dashboard/index.html#/rubro/{rid}/tema/{t}">{n} indicador{"es" if n > 1 else ""}</a></td>'
                )
            else:
                cells.append('<td class="pendiente">pendiente</td>')
        rows.append(
            f'<tr><th scope="row"><a href="rubros/{rid}/">{html.escape(r["nombre"])}</a></th>{"".join(cells)}</tr>'
        )
    return (
        '<div class="matriz" markdown="0"><table class="matriz-tabla"><thead><tr><th scope="col">Rubro \\ Tema</th>' + head + "</tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>\n\n"
        "*🟢 caso con resultado observado en datos reales · 🔵 caso con resultado estimado (escenario) · «n indicadores» abre el tablero "
        "filtrado · «pendiente»: todavía no hay un indicador de ese tema para ese rubro.*\n\n"
    )  # fmt: skip


def destacados(engine: Engine, manifest: dict, n: int = 3) -> list[str]:
    info = resumen_casos(engine, manifest)
    order = sorted(
        info,
        key=lambda c: (info[c]["tipo"] != "observado", not info[c]["reales"], list(info).index(c)),
    )
    return order[:n]


# ------------------------------------------------------------------ alertas por rubro
def alertas_rubro(
    engine: Engine, values: dict[str, Headline], vals: dict, rubro: str
) -> list[dict]:
    """Costliest alerts of a rubro: cases with a value in soles first, then KPIs in red or amber."""
    out = []
    for c in engine.catalog.cases_for_rubro(rubro):
        v = vals.get(c)
        if v is not None and v.soles_mes > 0:
            out.append({"titulo": v.titulo, "caso": c, "monto": v.soles_mes, "texto": v.resumen_brecha, "accion": v.accion,
                        "responsable": v.responsable, "fecha": v.fecha})  # fmt: skip
    seen = {a["caso"] for a in out}
    rank = {"red": 0, "amber": 1}
    ks = [
        k
        for k in engine.catalog.for_rubro(rubro)
        if k.case in engine.catalog.cases_for_rubro(rubro) and k.case not in seen
    ]
    ks = [k for k in ks if values.get(k.id) and engine.status(k.id, values[k.id].value) in rank]
    ks.sort(key=lambda k: rank[engine.status(k.id, values[k.id].value)])
    for k in ks:
        h = values[k.id]
        out.append({"titulo": k.name, "caso": k.case, "monto": None,
                    "texto": f"{format_value(k, h.value)} frente a la meta {format_threshold(k, with_alert=False)} ({h.period})",
                    "accion": k.decision, "responsable": k.owner, "fecha": "próxima revisión del indicador",
                    "estado": engine.status(k.id, h.value)})  # fmt: skip
    return out[:3]


def resumen_por_rubro(engine: Engine, values: dict[str, Headline], vals: dict) -> str:
    cfg = rubros_config()
    opts = "".join(
        f'<option value="{r}">{html.escape(d["nombre"])}</option>' for r, d in cfg["rubros"].items()
    )
    md = [
        "## Alertas más caras por rubro\n",
        f'<div class="rubro-selector" markdown="0"><label for="sel-rubro">Elija un rubro: </label><select id="sel-rubro" data-rubros>{opts}</select></div>\n',
    ]
    for i, (rid, d) in enumerate(cfg["rubros"].items()):
        al = alertas_rubro(engine, values, vals, rid)
        items = []
        for j, a in enumerate(al, start=1):
            monto = (
                f"{money(a['monto'])} al mes"
                if a["monto"]
                else f"{theme.STATUS_ICON[a['estado']]} {theme.STATUS_TEXT[a['estado']]} · sin costo estimado"
            )
            items.append(
                f"<li><b>{j} · {html.escape(a['titulo'])}</b> — {monto}<br>{html.escape(a['texto'])}<br>"
                f"<b>Acción:</b> {html.escape(a['accion'])} <b>Responsable:</b> {html.escape(a['responsable'])} · "
                f'<a href="../cases/{a["caso"]}/">ver el caso</a></li>'
            )
        body = (
            "<ol>" + "".join(items) + "</ol>"
            if items
            else "<p>Ningún indicador de este rubro está fuera de meta.</p>"
        )
        md.append(
            f'<section class="alertas-rubro" markdown="0" data-rubro="{rid}"{"" if i == 0 else " hidden"}>'
            f'<h3>{html.escape(d["nombre"])}</h3>{body}<p><a href="../rubros/{rid}/">Ver el rubro</a> · '
            f'<a href="../dashboard/index.html#/rubro/{rid}">Ver en el tablero</a></p></section>\n'
        )
    md.append(
        "*Los montos en soles solo existen donde hay supuestos de valor (los cinco casos con simulador). En los demás rubros la alerta "
        "muestra el indicador fuera de meta sin inventar un costo.*\n"
    )
    return "\n".join(md)
