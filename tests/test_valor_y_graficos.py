"""Tooltips completos, supuestos de valor válidos, cifras de impacto iguales en todo el sitio y gráficos que responden."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import pytest
import yaml

from kpistory.catalog import load
from kpistory.paths import PROCESSED_DIR, ROOT

SITE = ROOT / "site"
REQUIRE = os.environ.get("KPISTORY_REQUIRE_SITE") == "1"
C = load()
TIP_FIELDS = ("meaning", "calculation", "target_why", "decision", "balance", "owner")
ENGLISH = re.compile(r"\b(the|and|of|with|which|when|target|rate|should|this)\b", re.I)
SPANISH = re.compile(r"\b(de|la|el|los|las|que|en|un|una|por|se|con|del)\b", re.I)


# ------------------------------------------------------------------ tooltips
@pytest.mark.parametrize("kpi", list(C), ids=lambda k: k.id)
def test_cada_indicador_tiene_su_tooltip_completo_y_en_espanol(kpi):
    for field in TIP_FIELDS:
        text = getattr(kpi, field)
        assert text and len(text.strip()) >= 8, f"{kpi.id}.{field} vacío"
        if field != "owner":
            assert SPANISH.search(text), f"{kpi.id}.{field} no parece español: {text!r}"
        assert not ENGLISH.search(text), f"{kpi.id}.{field} tiene inglés: {text!r}"


# ------------------------------------------------------------------ supuestos de valor
def test_cada_supuesto_tiene_fuente_o_es_ilustrativo():
    cfg = yaml.safe_load((ROOT / "config" / "supuestos_valor.yaml").read_text(encoding="utf-8"))
    # Solo los casos con supuestos de costo defendibles tienen valor en soles; los demás muestran la alerta sin inventar un costo.
    assert (
        {"service", "maintenance", "inventory", "customers", "data_quality"}
        <= set(cfg["casos"])
        <= set(C.cases)
    )
    for caso, spec in cfg["casos"].items():
        assert spec["componentes"], caso
        for comp in spec["componentes"]:
            assert comp.get("fuente") or comp.get("ilustrativo") is True, (
                f"{caso}: falta fuente o ilustrativo"
            )
            assert comp["explicacion_costo"].strip() and comp["costo_unitario"] >= 0
            assert comp["indicador"] in C.kpis
        for campo in ("accion", "responsable", "plazo_dias", "efecto_decision"):
            assert campo in spec, f"{caso}: falta {campo}"


@pytest.fixture(scope="module")
def valores():
    if not (PROCESSED_DIR / "manifest.json").exists():
        if REQUIRE:
            pytest.fail("faltan los datos procesados")
        pytest.skip("corre `kpistory data` primero")
    from kpistory.data.pipeline import load_tables
    from kpistory.engine import Engine
    from kpistory.valor import valores as calc

    t, m = load_tables()
    return calc(t, Engine(), m)


def test_el_impacto_no_es_nulo_ni_negativo_sin_explicacion(valores):
    for caso, v in valores.items():
        assert v.soles_mes is not None and not math.isnan(v.soles_mes), caso
        assert v.soles_mes >= 0 and v.horas_mes >= 0, caso
        if v.soles_mes == 0:
            assert "En meta" in v.resumen_brecha, f"{caso}: impacto cero sin explicación"
        for c in v.componentes:
            assert c.unidades_de_mas >= 0 and c.soles_mes == pytest.approx(
                c.unidades_de_mas * c.costo_unitario
            )


def test_impacto_calculado_a_mano():
    """227 abiertas, 76.7 % antiguas, meta 10 %, S/ 60 por pendiente: (0.767 - 0.10) x 227 x 60 = S/ 9 084.5."""
    from kpistory.valor import gap

    assert gap(0.767, 0.10, "lower_is_better") == pytest.approx(0.667)
    assert gap(0.95, 0.90, "higher_is_better") == 0.0  # en meta: no cuesta
    assert 227 * gap(0.767, 0.10, "lower_is_better") * 60 == pytest.approx(9084.54)


# ------------------------------------------------------------------ sitio publicado
def _site():
    if not SITE.exists():
        if REQUIRE:
            pytest.fail("No existe site/")
        pytest.skip("site/ no existe")
    return pytest.importorskip("bs4")


def _dashboard() -> dict:
    src = (SITE / "dashboard" / "index.html").read_text(encoding="utf-8")
    return json.loads(src.split("const DATA =", 1)[1].split(";\nconst ICON", 1)[0])


def test_las_cifras_de_impacto_coinciden_en_portada_resumen_casos_y_tablero():
    bs4 = _site()
    soup = lambda p: bs4.BeautifulSoup((SITE / p).read_text(encoding="utf-8"), "html.parser")  # noqa: E731
    d = _dashboard()["valor"]
    total = round(d["total_anio"])
    portada = soup("index.html").select_one("[data-valor-total]")["data-valor-total"]
    resumen = soup("resumen/index.html").select_one("[data-valor-total]")["data-valor-total"]
    assert int(portada) == int(resumen) == total
    por_caso = {c["caso"]: round(c["soles_mes"]) for c in d["casos"]}
    for caso, mes in por_caso.items():
        card = soup(f"cases/{caso}/index.html").select_one(f'.valor-card[data-caso="{caso}"]')
        assert int(card["data-valor-mes"]) == mes, caso
    for card in soup("resumen/index.html").select(".valor-card[data-caso]"):
        assert int(card["data-valor-mes"]) == por_caso[card["data-caso"]]
    assert (
        d["top"]
        == sorted(
            [c["caso"] for c in d["casos"] if c["soles_mes"] > 0],
            key=lambda c: -[x for x in d["casos"] if x["caso"] == c][0]["soles_anio"],
        )[:3]
    )


def _layout_title(script: str) -> str:
    """Decode Plotly.newPlot(id, data, layout, ...) and return layout.title.text (tags removed)."""
    dec = json.JSONDecoder()
    i = script.find("Plotly.newPlot(")
    if i < 0:
        return ""
    i = script.index(",", i) + 1  # skip the div id
    while script[i] in " \n\t":
        i += 1
    _, end = dec.raw_decode(script, i)  # data
    i = script.index(",", end) + 1
    while script[i] in " \n\t":
        i += 1
    layout, _ = dec.raw_decode(script, i)
    title = layout.get("title") or {}
    text = title.get("text", "") if isinstance(title, dict) else str(title)
    return re.sub(r"<[^>]+>", " ", text).strip()


def test_cada_grafico_tiene_titulo_respuesta_y_su_tabla():
    bs4 = _site()
    names = {k.name.lower() for k in C}
    problems = []
    for page in SITE.rglob("index.html"):
        if "dashboard" in page.parts:
            continue
        soup = bs4.BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for chart in soup.select("div.chart"):
            if chart.find_parent(class_="bad"):
                continue  # the misleading half of the error gallery is wrong on purpose
            script = chart.find("script")
            title = _layout_title(script.string or "") if script else ""
            where = f"{page.relative_to(SITE)}"
            if not title or title.lower() in names:
                problems.append(
                    f"{where}: título vacío o igual al nombre del indicador ({title!r})"
                )
            nxt = chart.find_next_sibling()
            while (
                nxt is not None and nxt.name == "p" and "chart-caption" in (nxt.get("class") or [])
            ):
                nxt = nxt.find_next_sibling()
            if nxt is None or nxt.name != "details" or "data" not in (nxt.get("class") or []):
                problems.append(f"{where}: gráfico sin «Ver datos» ({title[:50]!r})")
    assert not problems, "\n".join(problems)


def test_tarjetas_con_tooltip_accesible():
    bs4 = _site()
    soup = bs4.BeautifulSoup(
        (SITE / "cases" / "service" / "index.html").read_text(encoding="utf-8"), "html.parser"
    )
    tiles = soup.select("a.kpi-tile")
    assert tiles
    for a in tiles:
        tip = soup.find(id=a["aria-describedby"])
        assert tip is not None and tip.get("role") == "tooltip" and not a.get("title")
        rule = soup.find(id=a.select_one(".kpi-status")["aria-describedby"])
        assert rule is not None and rule.get("role") == "tooltip"
    src = (SITE / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert (
        'role="tooltip"' in src
        and "aria-describedby" in src
        and " title=" not in src.split("<script>")[0]
    )
    assert all(k["target_why"] and k["calculation"] for k in _dashboard()["kpis"])


def test_los_textos_del_tablero_estan_en_espanol():
    _site()
    src = (SITE / "dashboard" / "index.html").read_text(encoding="utf-8")
    for es in ("Tablero de indicadores", "Todos los rubros", "Todos los temas", "Cualquier estado", "En meta", "Vigilar", "Actuar",
               "Cómo leerlo", "Errores comunes de lectura", 'locale: "es"'):  # fmt: skip
        assert es in src, es
    for en in (
        "KPI Dashboard",
        "Any status",
        "HOW TO READ",
        "COMMON MISREADINGS",
        "On target",
        "Why this exists",
    ):
        assert en not in src, en


@pytest.mark.skipif(not Path(ROOT / "includes" / "glosario.md").exists(), reason="sin glosario")
def test_glosario_define_las_siglas():
    text = (ROOT / "includes" / "glosario.md").read_text(encoding="utf-8")
    for sigla in ("SLA", "FCR", "KPI", "MTBF", "MTTR", "P90", "backlog", "indicador adelantado"):
        assert f"*[{sigla}]:" in text, sigla
