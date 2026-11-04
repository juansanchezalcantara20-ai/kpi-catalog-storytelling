"""Descarga robusta, conexión con NYC 311 y candado de privacidad (sin internet: la red se simula)."""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from kpistory.data import download, pipeline, solicitudes311, tickets
from kpistory.engine import Engine
from kpistory.privacidad import check_site, check_tables

E = Engine()


def fake_311(n: int = 6000, seed: int = 1) -> pd.DataFrame:
    """Rows shaped like the public NYC 311 CSV (only the allowed columns)."""
    rng = np.random.default_rng(seed)
    created = pd.Timestamp("2024-11-01") + pd.to_timedelta(rng.uniform(0, 365, n), unit="D")
    hours = rng.lognormal(np.log(48), 1.2, n)
    closed = created + pd.to_timedelta(hours, unit="h")
    closed = closed.where(rng.random(n) > 0.05)  # some never closed
    types = rng.choice(
        [
            "Street Light Condition",
            "Street Condition",
            "Traffic Signal Condition",
            "Sidewalk Condition",
            "Noise",
        ],
        n,
    )
    return pd.DataFrame(
        {
            "unique_key": np.arange(60000000, 60000000 + n).astype(str),
            "created_date": created.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "closed_date": pd.Series(closed).dt.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "agency": "DOT",
            "complaint_type": types,
            "open_data_channel_type": rng.choice(["PHONE", "ONLINE", "MOBILE", "UNKNOWN"], n),
            "status": "Closed",
            "borough": rng.choice(["BROOKLYN", "QUEENS", "MANHATTAN"], n),
        }
    )


def _pages(df: pd.DataFrame, size: int):
    """Fake HTTP getter serving `df` as CSV pages for $limit/$offset."""
    calls = []

    def get(url: str, timeout: int) -> bytes:
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(url).query)
        off, lim = int(q["$offset"][0]), int(q["$limit"][0])
        calls.append(off)
        buf = io.StringIO()
        df.iloc[off : off + lim].to_csv(buf, index=False)
        return buf.getvalue().encode()

    return get, calls


def test_paginacion_baja_todas_las_paginas():
    df = fake_311(2500)
    get, calls = _pages(df, 1000)
    out = download.fetch_paged_csv(
        "https://x/api.csv",
        {},
        page_size=1000,
        max_rows=10_000,
        min_rows=100,
        get=get,
        log=lambda m: None,
    )
    assert len(out) == 2500 and calls == [0, 1000, 2000]


def test_falla_si_llegan_menos_filas_que_el_minimo():
    get, _ = _pages(fake_311(50), 1000)
    with pytest.raises(download.DownloadError, match="mínimo"):
        download.fetch_paged_csv(
            "https://x/api.csv",
            {},
            page_size=1000,
            max_rows=10_000,
            min_rows=100,
            get=get,
            log=lambda m: None,
        )


def test_reintenta_antes_de_rendirse():
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError("red caída")
        return b"ok"

    assert download.with_retries(flaky, retries=4, sleep=lambda s: None) == b"ok"
    assert len(attempts) == 3
    with pytest.raises(download.DownloadError):
        download.with_retries(
            lambda: (_ for _ in ()).throw(OSError("siempre")), retries=2, sleep=lambda s: None
        )


def test_ventana_de_doce_meses_completos():
    cfg = solicitudes311.config()
    start, cutoff = solicitudes311.window(cfg, today=pd.Timestamp("2026-11-04"))
    assert (start, cutoff) == (pd.Timestamp("2025-11-01"), pd.Timestamp("2026-11-01"))


def test_mapeo_a_solicitudes_en_espanol():
    cfg = solicitudes311.config()
    raw = fake_311(3000)
    landing = solicitudes311.to_tickets(raw, cfg, snapshot=pd.Timestamp("2025-10-31 23:59"))
    assert set(landing["priority"]) <= {"Urgente", "Alta", "Media", "Baja"}
    assert "Semáforos" in set(landing["queue"]) and "Otros" in set(landing["queue"])
    assert set(landing["channel"]) <= {"Teléfono", "Web", "App móvil", "Otro"}
    assert landing.loc[landing["queue"].eq("Semáforos"), "sla_target_hours"].eq(24).all()
    # Closed after the cut-off = still open at the snapshot.
    late = pd.to_datetime(raw["closed_date"]) > pd.Timestamp("2025-10-31 23:59")
    assert landing.loc[late.values, "status"].eq("open").all()
    clean = tickets.clean(landing, pd.Timestamp("2025-10-31 23:59"))
    assert 0 <= E.compute("sla_compliance", clean) <= 1
    assert 0 <= E.compute("backlog_aged_share", clean) <= 1


def test_rechaza_columnas_personales():
    cfg = solicitudes311.config()
    raw = fake_311(10).assign(incident_address="123 MAIN STREET")
    with pytest.raises(ValueError, match="no permitidas"):
        solicitudes311.to_tickets(raw, cfg, snapshot=pd.Timestamp("2025-10-31"))


def test_si_falla_la_descarga_usa_el_plan_b_y_lo_dice(monkeypatch):
    def broken(*a, **k):
        raise download.DownloadError("sin red")

    monkeypatch.setattr(solicitudes311, "download", broken)
    landing, clean, info = pipeline._tickets("auto")
    assert info["origin"] == "synthetic" and "falló" in info["note"]
    assert len(clean) > 1000


def test_con_datos_reales_marca_los_indicadores_sin_dato(monkeypatch):
    raw = fake_311(6000)
    info = {"name": "NYC 311", "publisher": "x", "url": "https://x", "downloaded_at": "2025-11-02", "rows": len(raw),
            "filter": "f", "snapshot": "2025-10-31 23:59"}  # fmt: skip
    monkeypatch.setattr(solicitudes311, "download", lambda cfg=None: (raw, dict(info)))
    landing, clean, meta = pipeline._tickets("auto")
    assert meta["origin"] == "real"
    assert set(meta["unavailable_kpis"]) == {
        "first_response_time",
        "first_contact_resolution",
        "reopen_rate",
    }


def test_candado_de_privacidad(tmp_path):
    site = tmp_path / "site"
    (site / "p").mkdir(parents=True)
    (site / "p" / "index.html").write_text(
        "<p>Llamar al (212) 555-0199 o escribir a vecino@correo.com</p>", encoding="utf-8"
    )
    (site / "datos.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    problems = " ".join(check_site(site))
    assert "teléfono" in problems and "datos.csv" in problems
    (site / "p" / "index.html").write_text(
        "<p>Reclamo en 742 EVERGREEN AVENUE</p>", encoding="utf-8"
    )
    assert any("dirección" in p for p in check_site(site))
    (site / "datos.csv").unlink()
    (site / "p" / "index.html").write_text(
        "<p>89.2 % de 10 637 solicitudes, 31 dic 2024</p>", encoding="utf-8"
    )
    assert check_site(site) == []


def test_candado_revisa_las_columnas(tmp_path):
    pd.DataFrame({"ticket_id": ["a"], "incident_address": ["x"]}).to_parquet(
        tmp_path / "landing_tickets.parquet"
    )
    assert check_tables(tmp_path)
