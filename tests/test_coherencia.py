"""Coherencia de las cifras: rangos posibles, denominadores correctos y el mismo número en todo el sitio."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import pytest

from kpistory.engine import Engine
from kpistory.paths import PROCESSED_DIR

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REQUIRE = os.environ.get("KPISTORY_REQUIRE_SITE") == "1"
E = Engine()


@pytest.fixture(scope="module")
def data():
    if not (PROCESSED_DIR / "manifest.json").exists():
        if REQUIRE:
            pytest.fail("faltan los datos procesados: corre `kpistory data`")
        pytest.skip("corre `kpistory data` primero")
    from kpistory.data.pipeline import load_tables

    return load_tables()


def test_ningun_porcentaje_fuera_de_0_a_100(data):
    from kpistory.site.current import headline

    tables, manifest = data
    for kid, h in headline(tables, E, manifest).items():
        k = E.catalog[kid]
        if math.isnan(h.value):
            continue
        if k.unit == "percent" and k.direction != "target_range":
            assert 0 <= h.value <= 1, f"{kid} = {h.value}"
        if k.unit == "score":
            assert -100 <= h.value <= 100, kid
        if k.unit in ("hours", "days", "times_per_year"):
            assert h.value >= 0, kid


def test_pendientes_antiguas_usa_solo_las_abiertas_al_corte(data):
    """Caso 1: el denominador son las solicitudes abiertas a la fecha de corte, no todas."""
    tables, _ = data
    tk = tables["tickets"]
    abiertas = tk[tk["status"].eq("open")]
    esperado = (abiertas["age_days"] > 7).sum() / len(abiertas)
    assert E.compute("backlog_aged_share", tk) == pytest.approx(esperado)
    # Las cerradas no tienen antigüedad: no pueden entrar ni al numerador ni al denominador.
    assert tk.loc[tk["status"].eq("resolved"), "age_days"].isna().all()
    # Y el tiempo de resolución solo mira las cerradas.
    cerradas = tk[tk["status"].eq("resolved")]
    assert E.compute("resolution_time", tk) == pytest.approx(cerradas["resolution_hours"].median())


def _site_values() -> tuple[dict, dict, dict]:
    if not SITE.exists():
        if REQUIRE:
            pytest.fail("No existe site/: corre `mkdocs build`.")
        pytest.skip("site/ no existe")
    bs4 = pytest.importorskip("bs4")
    tiles = {}
    for page in (SITE / "cases").rglob("index.html"):
        soup = bs4.BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for a in soup.select("a.kpi-tile"):
            tiles[a["data-kpi"]] = a.select_one(".kpi-value").get_text(strip=True)
    catalog = {}
    for kid in E.catalog.kpis:
        soup = bs4.BeautifulSoup(
            (SITE / "catalog" / kid / "index.html").read_text(encoding="utf-8"), "html.parser"
        )
        line = next(p for p in soup.find_all("p") if p.get_text().startswith("Valor actual"))
        catalog[kid] = line.get_text(" ", strip=True)
    src = (SITE / "dashboard" / "index.html").read_text(encoding="utf-8")
    payload = json.loads(src.split("const DATA =", 1)[1].split(";\nconst ICON", 1)[0])
    dashboard = {k["id"]: k["display"] for k in payload["kpis"]}
    return tiles, catalog, dashboard


def test_caso_catalogo_y_tablero_muestran_la_misma_cifra():
    tiles, catalog, dashboard = _site_values()
    assert set(tiles) == set(E.catalog.kpis), "cada indicador debe tener su tarjeta en algún caso"
    for kid, value in tiles.items():
        assert dashboard[kid] == value, f"{kid}: caso {value!r} vs tablero {dashboard[kid]!r}"
        if value != "Sin dato":
            assert value in catalog[kid], f"{kid}: caso {value!r} vs catálogo {catalog[kid]!r}"


def test_formato_unico_de_porcentaje():
    tiles, _, _ = _site_values()
    for kid, value in tiles.items():
        if E.catalog[kid].unit == "percent" and value != "Sin dato":
            assert re.fullmatch(r"-?\d+\.\d %", value), f"{kid}: {value!r}"
