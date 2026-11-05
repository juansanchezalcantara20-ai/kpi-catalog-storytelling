"""Ingest -> clean -> derive every table used by the cases; write data/processed/*.parquet.

`source`:
  auto       try the public download; on any failure use the seeded synthetic plan B
  real       public download only (fail loudly if unavailable)
  synthetic  plan B only (fully offline and deterministic; used by CI tests)

The provenance of every dataset is written to data/processed/manifest.json and shown
on the site, so a reader always knows whether a chart comes from real or synthetic data.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd

from ..paths import PROCESSED_DIR
from . import customers, inventory, maintenance, quality, retail, sectores, solicitudes311, tickets

SOURCES = {
    "process_data": {
        "name": "AI4I 2020 (datos de proceso de máquinas)",
        "publisher": "UCI Machine Learning Repository (Matzka, 2020), CC BY 4.0",
        "url": "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset",
        "tipo": "referencia",
    },
    "transactions": {
        "name": "Online Retail II (ventas de una tienda en línea)",
        "publisher": "UCI Machine Learning Repository (Chen, 2019), CC BY 4.0",
        "url": retail.URL,
    },
}


def _acquire(
    name: str, real: Callable[[], pd.DataFrame], synthetic: Callable[[], pd.DataFrame], source: str
):
    info = dict(SOURCES[name])
    if source in ("auto", "real"):
        try:
            t0 = time.time()
            df = real()
            info.update(
                origin="real",
                note=f"descargado y leído en {time.time() - t0:.0f} s",
                downloaded_at=datetime.now(UTC).strftime("%Y-%m-%d"),
            )
            return df, info
        except Exception as exc:
            if source == "real":
                raise
            info.update(origin="synthetic", note=f"plan B - la descarga falló: {str(exc)[:160]}")
    else:
        info.update(origin="synthetic", note="plan B - se pidieron datos simulados")
    return synthetic(), info


SECTOR_SOURCES = [
    ("energia", "energia_anual", sectores.energia_real, sectores.energia_sintetica),
    ("salud", "salud_semanal", sectores.salud_real, sectores.salud_sintetica),
    ("moviles", "moviles_anual", sectores.moviles_real, sectores.moviles_sintetica),
    ("docentes", "docentes", sectores.docentes_real, sectores.docentes_sintetica),
    ("vuelos", "vuelos", sectores.vuelos_real, sectores.vuelos_sintetica),
]
SECTOR_NAMES = {
    "energia": "energia",
    "salud": "mortalidad",
    "moviles": "moviles",
    "docentes": "docentes",
    "vuelos": "vuelos",
}


def _sector(
    key: str, real: Callable, synthetic: Callable, source: str
) -> tuple[pd.DataFrame, dict]:
    cfg = sectores.fuentes()[SECTOR_NAMES[key]]
    info = {"name": cfg["nombre"], "publisher": cfg["publicador"], "url": cfg["pagina"]}
    if key == "salud":  # two files of the same publisher
        info.update(name="COVID-19: vacunación y muertes confirmadas por semana (Our World in Data)",
                    url="https://github.com/owid/covid-19-data")  # fmt: skip
    if source in ("auto", "real"):
        try:
            t0 = time.time()
            df, extra = real()
            info.update(origin="real", rows=extra["rows"], filter=extra["filter"],
                        note=f"{extra['rows']} filas en {time.time() - t0:.0f} s; {extra['filter']}",
                        downloaded_at=datetime.now(UTC).strftime("%Y-%m-%d"))  # fmt: skip
            return df, info
        except Exception as exc:
            if source == "real":
                raise
            reason = f"plan B - la descarga falló: {type(exc).__name__}: {str(exc)[:160]}"
    else:
        reason = "plan B - se pidieron datos simulados"
    df = synthetic()
    info.update(
        name=cfg["nombre"] + " (simulados)",
        origin="synthetic",
        rows=len(df),
        note=f"{reason}; semilla fija",
    )
    return df, info


UNAVAILABLE_IN_311 = ["first_response_time", "first_contact_resolution", "reopen_rate"]


def _tickets(source: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if source in ("auto", "real"):
        try:
            cfg = solicitudes311.config()
            t0 = time.time()
            raw, info = solicitudes311.download(cfg)
            snapshot = pd.Timestamp(info["snapshot"])
            landing = solicitudes311.to_tickets(raw, cfg, snapshot)
            info.update(origin="real", note=f"{info['rows']} solicitudes descargadas en {time.time() - t0:.0f} s; {info['filter']}",
                        unavailable_kpis=UNAVAILABLE_IN_311)  # fmt: skip
            return landing, tickets.clean(landing, snapshot), info
        except Exception as exc:
            if source == "real":
                raise
            reason = f"plan B - la descarga falló: {type(exc).__name__}: {str(exc)[:160]}"
    else:
        reason = "plan B - se pidieron datos simulados"
    landing = tickets.generate()
    info = {
        "name": "Solicitudes de una mesa de ayuda (simuladas)",
        "origin": "synthetic",
        "note": f"{reason}; simulación de colas, semilla {tickets.SEED}",
        "snapshot": f"{tickets.SNAPSHOT:%Y-%m-%d %H:%M}",
        "unavailable_kpis": [],
    }
    return landing, tickets.clean(landing), info


def build(source: str = "auto") -> tuple[dict[str, pd.DataFrame], dict]:
    manifest: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_mode": source,
    }
    landing: dict[str, pd.DataFrame] = {}
    tables: dict[str, pd.DataFrame] = {}

    # Case 1 - service requests: NYC 311 (public) or the synthetic queue simulation
    landing["tickets"], tables["tickets"], manifest["tickets"] = _tickets(source)

    # Case 2 - maintenance
    ai4i, manifest["process_data"] = _acquire(
        "process_data", maintenance.load_real, maintenance.generate_ai4i, source
    )
    landing["process_data"] = ai4i
    runs = maintenance.runs_from_process(ai4i)
    landing["work_orders"] = maintenance.generate_work_orders(runs)
    tables["runs"] = runs
    tables["work_orders"] = maintenance.clean_work_orders(landing["work_orders"])
    tables["asset_periods"] = maintenance.asset_periods(runs, tables["work_orders"])
    manifest["work_orders"] = {
        "name": "Órdenes de trabajo de mantenimiento (simuladas)",
        "origin": "synthetic",
        "note": f"generadas a partir de las fallas de los datos de proceso, semilla {maintenance.SEED}",
    }

    # Cases 3 and 4 - retail demand and customers
    trx, manifest["transactions"] = _acquire(
        "transactions", retail.load_real, retail.generate, source
    )
    landing["transactions"] = trx
    tables["sales"] = retail.clean(trx)
    tables.update(inventory.simulate(tables["sales"]))
    manifest["inventory"] = {
        "name": "Inventario, reposición y entregas (simulados)",
        "origin": "synthetic",
        "note": f"simulación de una política de reposición sobre la demanda anterior, semilla {inventory.SEED}",
    }
    tables["customer_sales"] = customers.identified_sales(tables["sales"])
    tables["customer_rfm"] = customers.build_rfm(tables["sales"])
    landing["survey"] = customers.generate_survey(tables["customer_rfm"])
    tables["survey"] = customers.clean_survey(landing["survey"])
    manifest["survey"] = {
        "name": "Encuesta de recomendación (simulada)",
        "origin": "synthetic",
        "note": f"notas generadas según el segmento del cliente, semilla {customers.SEED}",
    }

    # Case 5 - data quality on the landing data
    tables.update(quality.measure(landing))

    # Sector cases: public data compared by group, each with its own plan B
    for key, table, real, synthetic in SECTOR_SOURCES:
        tables[table], manifest[key] = _sector(key, real, synthetic, source)
    tables["creditos"] = sectores.creditos_sintetica()
    manifest["creditos"] = {"name": sectores.fuentes()["creditos"]["nombre"], "origin": "synthetic",
                            "note": "simulación de una cartera de créditos, semilla 2031 (no hay fuente pública estable sin registro)"}  # fmt: skip
    return {**tables, **{f"landing_{k}": v for k, v in landing.items()}}, manifest


def _text_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Object columns that mix types (e.g. numbers typed into a text field) become strings for Parquet."""
    out = df.copy()
    for col in out.columns[out.dtypes.eq(object)]:
        kinds = out[col].dropna().map(type).unique()
        if len(kinds) > 1:
            out[col] = out[col].map(lambda v: None if pd.isna(v) else str(v)).astype("string")
    return out


def run(source: str = "auto") -> dict:
    t0 = time.time()
    try:
        tables, manifest = build(source)
        tables = {name: _text_safe(df) for name, df in tables.items()}
    except Exception as exc:
        if source != "auto":
            raise
        # Real data downloaded but broke a later step: publish plan B rather than nothing, and say why.
        print(
            f"  real-data build failed ({type(exc).__name__}: {str(exc)[:200]}); rebuilding with plan B"
        )
        tables, manifest = build("synthetic")
        manifest["source_mode"] = (
            "auto (volvió a datos simulados tras un error con los datos reales)"
        )
        for key in ("tickets", "process_data", "transactions"):
            manifest[key]["note"] = (
                f"plan B - los datos reales fallaron más adelante: {type(exc).__name__}: {str(exc)[:160]}"
            )
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
    manifest["tables"] = {name: len(df) for name, df in tables.items()}
    (PROCESSED_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for key in (
        "tickets",
        "process_data",
        "work_orders",
        "transactions",
        "inventory",
        "survey",
        *SECTOR_NAMES,
        "creditos",
    ):
        print(f"  {key:<14} {manifest[key]['origin']:<9} {manifest[key]['note']}")
    print(f"Data ready in {time.time() - t0:.0f}s -> {PROCESSED_DIR}")
    return manifest


def load_tables() -> tuple[dict[str, pd.DataFrame], dict]:
    """Read every processed table (run `kpistory data` first)."""
    manifest_path = PROCESSED_DIR / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("No processed data. Run `python -m kpistory data` first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tables = {
        name: pd.read_parquet(PROCESSED_DIR / f"{name}.parquet") for name in manifest["tables"]
    }
    return tables, manifest
