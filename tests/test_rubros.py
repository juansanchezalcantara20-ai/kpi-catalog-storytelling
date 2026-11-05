"""Rubros (sectores) y temas: cobertura, plantilla de casos, resultados honestos y privacidad.

Las pruebas que miran el sitio publicado necesitan `mkdocs build` (corren en `make legibilidad`).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import yaml

from kpistory.catalog import load, rubros_config

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PROCESSED = ROOT / "data" / "processed"
REQUIRE = os.environ.get("KPISTORY_REQUIRE_SITE") == "1"
C = load()
CFG = rubros_config()
FUENTES = yaml.safe_load((ROOT / "config" / "fuentes.yaml").read_text(encoding="utf-8"))
OBSERVADO = "Resultado observado en datos reales"
ESTIMADO = "Resultado estimado (escenario)"


def _site() -> None:
    if not SITE.exists():
        if REQUIRE:
            pytest.fail("No existe site/: corre `mkdocs build` antes de esta prueba.")
        pytest.skip("site/ no existe; corre `make all` primero")


def _soup(rel: str):
    bs4 = pytest.importorskip("bs4")
    return bs4.BeautifulSoup((SITE / rel / "index.html").read_text(encoding="utf-8"), "html.parser")


# ------------------------------------------------------------------ catálogo y configuración
@pytest.mark.parametrize("rubro", list(CFG["rubros"]))
def test_cada_rubro_tiene_caso_indicadores_y_fuente(rubro):
    casos = C.cases_for_rubro(rubro)
    assert casos, f"{rubro}: sin caso"
    assert len(C.for_rubro(rubro)) >= 6, f"{rubro}: menos de 6 indicadores"
    r = CFG["rubros"][rubro]
    assert len(r["como_gana"]) == 3 and len(r["errores"]) == 2, rubro
    fuentes = {k for c in casos for k in C.cases[c]["fuentes"]}
    assert fuentes, rubro
    for k in fuentes:
        f = FUENTES[k]
        for campo in ("nombre", "publicador", "licencia", "tipo", "rubros"):
            assert f.get(campo), f"{k}: falta {campo}"
        if f["tipo"] in ("real", "referencia"):
            assert str(f.get("pagina", "")).startswith("https://"), k
            assert str(f.get("descarga") or f.get("api") or "").startswith("https://"), k


def test_cada_tema_existe_y_cada_indicador_tiene_tema_y_rubros():
    for k in C:
        assert k.tema in CFG["temas"], k.id
        assert k.rubros and set(k.rubros) <= set(CFG["rubros"]), k.id
    assert {k.tema for k in C} == set(CFG["temas"]), "un tema sin indicadores"


def test_un_resultado_observado_exige_evento_con_fuentes():
    for cid, c in C.cases.items():
        if c["resultado"] == "observado":
            ev = c["evento"]
            assert ev["fuentes"] and all(u.startswith("https://") for u in ev["fuentes"]), cid
            assert re.match(r"\d{4}-\d{2}-\d{2}$", ev["fecha"]), cid
            assert all(FUENTES[k]["tipo"] == "real" for k in c["fuentes"]), (
                f"{cid}: observado con fuente no real"
            )
        else:
            assert "evento" not in c, cid
    assert sum(c["resultado"] == "observado" for c in C.cases.values()) >= 2


def test_cada_caso_declara_resultado_adelantado_y_contrapeso():
    for cid, c in C.cases.items():
        roles = c["indicadores"]
        for rol in ("resultado", "adelantados", "contrapeso"):
            assert roles.get(rol) or (roles.get("pendientes") or {}).get(rol), f"{cid}: falta {rol}"


# ------------------------------------------------------------------ sitio publicado
@pytest.mark.parametrize("case", list(C.cases))
def test_cada_caso_tiene_las_siete_partes_y_un_resultado_etiquetado(case):
    _site()
    soup = _soup(f"cases/{case}")
    content = soup.select_one("article") or soup
    titles = [p.get_text(strip=True) for p in content.select(".admonition-title")]
    assert "En 30 segundos" in titles, case
    h2 = [h.get_text(" ", strip=True).replace("¶", "").strip() for h in content.find_all("h2")]
    orden = ["Problema", "Indicadores", "Análisis", "Solución", "Resultado"]
    assert [h for h in h2 if h in orden] == orden, f"{case}: secciones {h2}"
    assert content.select("details.tecnico"), f"{case}: sin detalle técnico"
    etiquetas = [t for t in titles if t in (OBSERVADO, ESTIMADO)]
    assert len(etiquetas) == 1, f"{case}: etiquetas de resultado {etiquetas}"
    meta = content.select_one(".caso-meta")
    assert meta is not None and meta["data-caso"] == case
    if etiquetas[0] == OBSERVADO:
        assert meta["data-resultado"] == "observado" and meta["data-reales"] == "1", case
        box = next(
            a
            for a in content.select(".admonition")
            if a.select_one(".admonition-title").get_text(strip=True) == OBSERVADO
        )
        links = {a["href"] for a in box.find_all("a", href=True)}
        assert set(C.cases[case]["evento"]["fuentes"]) <= links, (
            f"{case}: el resultado observado no enlaza su fuente"
        )
    else:
        assert meta["data-resultado"] == "estimado", case
    tiles = content.select(".kpi-tile")
    assert tiles and all(t.select_one(".kpi-rol") for t in tiles), f"{case}: tarjetas sin rol"


@pytest.mark.parametrize("rubro", list(CFG["rubros"]))
def test_pagina_de_rubro(rubro):
    _site()
    soup = _soup(f"rubros/{rubro}")
    text = soup.get_text(" ", strip=True)
    assert "Cómo gana dinero este rubro" in text and "Dos errores comunes" in text
    n = len(soup.select(".kpi-grid .kpi-tile"))
    assert 6 <= n <= 8, f"{rubro}: {n} tarjetas"
    hrefs = [a["href"] for a in soup.find_all("a", href=True)]
    assert any(re.search(rf"dashboard/(index\.html)?#/rubro/{rubro}$", h) for h in hrefs), (
        "falta «Ver en el tablero»"
    )
    assert any("/cases/" in h for h in hrefs), "sin enlace a sus casos"


def test_portada_matriz_contador_y_destacados():
    _site()
    soup = _soup(".")
    tabla = soup.select_one(".matriz table")
    filas = tabla.select("tbody tr")
    assert len(filas) == len(CFG["rubros"])
    assert all(len(f.find_all("td")) == len(CFG["temas"]) for f in filas)
    assert tabla.select("td.pendiente"), "la matriz debe mostrar las celdas pendientes"
    c = soup.select_one(".contador")
    obs, est = int(c["data-observados"]), int(c["data-estimados"])
    assert obs + est == len(C.cases)
    observados = [
        m
        for m in (SITE / "cases").glob("*/index.html")
        if 'data-resultado="observado"' in m.read_text(encoding="utf-8")
    ]
    assert obs == len(observados)


def test_resumen_tiene_selector_de_rubro():
    _site()
    soup = _soup("resumen")
    opts = [o["value"] for o in soup.select("#sel-rubro option")]
    assert opts == list(CFG["rubros"])
    assert {s["data-rubro"] for s in soup.select(".alertas-rubro")} == set(CFG["rubros"])


def test_tablero_filtra_por_rubro_y_tema():
    _site()
    src = (SITE / "dashboard" / "index.html").read_text(encoding="utf-8")
    data = json.loads(src.split("const DATA =", 1)[1].split(";\nconst ICON", 1)[0])
    assert set(data["rubros"]) == set(CFG["rubros"]) and set(data["temas"]) == set(CFG["temas"])
    for r in CFG["rubros"]:
        assert sum(r in k["rubros"] for k in data["kpis"]) >= 6, r
    assert all(k["tema"] in CFG["temas"] for k in data["kpis"])
    for token in ('"rubro"', '"tema"', "hashOf", "readHash"):
        assert token in src


def test_fuentes_se_generan_desde_la_configuracion():
    _site()
    text = _soup("data-sources").get_text(" ", strip=True)
    for k, f in FUENTES.items():
        if isinstance(f, dict) and "tipo" in f:
            assert f["nombre"] in text, k
            assert f["licencia"] in text, k
    assert "Fuentes que se evaluaron y no se usaron" in text


# ------------------------------------------------------------------ privacidad y tono
# «name» a secas es el nombre de un indicador o de un grupo; lo personal es el nombre de una persona.
PERSONALES = re.compile(r"(customer|client|cliente|first|last|full|contact|person|persona)_?(name|nombre)|(^|_)(email|correo|phone|"
                        r"telefono|address|direccion_postal|domicilio|street|calle|dni|ruc|latitude|longitude|lat|lon|descriptor)($|_)", re.I)  # fmt: skip


def test_ninguna_tabla_publicada_tiene_columnas_de_datos_personales():
    pd = pytest.importorskip("pandas")
    if not PROCESSED.exists():
        pytest.skip("sin datos procesados")
    for path in PROCESSED.glob("*.parquet"):
        cols = pd.read_parquet(path).columns
        bad = [c for c in cols if PERSONALES.search(str(c).replace(" ", "_"))]
        assert not bad, f"{path.name}: {bad}"


def test_el_tablero_no_publica_columnas_personales():
    _site()
    src = (SITE / "dashboard" / "index.html").read_text(encoding="utf-8")
    data = json.loads(src.split("const DATA =", 1)[1].split(";\nconst ICON", 1)[0])

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)

    assert not [k for k in keys(data) if PERSONALES.search(k)]


BUSQUEDA = re.compile(
    r"postul[éeóa]|postulaci[óo]n|vacante|b[úu]squeda de (empleo|trabajo)|reclutador|entrevista de trabajo",
    re.I,
)


def test_no_hay_referencias_a_la_busqueda_de_empleo():
    files = [ROOT / "README.md", *(ROOT / "docs").glob("*.md"), *(ROOT / "config").glob("*.yaml"), ROOT / "kpis" / "catalog.yaml",
             *(ROOT / "cases").glob("*.md")]  # fmt: skip
    if SITE.exists():
        files += list(SITE.rglob("*.html"))
    hits = [f"{p.relative_to(ROOT)}: «{m.group(0)}»" for p in files if p.exists()
            for m in [BUSQUEDA.search(p.read_text(encoding="utf-8"))] if m]  # fmt: skip
    assert not hits, hits


def test_la_prueba_de_legibilidad_cubre_las_paginas_nuevas():
    _site()
    from test_legibilidad import _pages

    rel = {str(p.relative_to(SITE)) for p in _pages()}
    for r in CFG["rubros"]:
        assert f"rubros/{r}/index.html" in rel
    for t in CFG["temas"]:
        assert f"temas/{t}/index.html" in rel
    for c in C.cases:
        assert f"cases/{c}/index.html" in rel
