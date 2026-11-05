"""Case 1 real data: NYC 311 Service Requests (NYC Open Data, Socrata API, no key needed).

Only non-personal columns are requested (see config/fuentes.yaml): no addresses,
coordinates, names or free-text descriptions. Rows are mapped to the ticket schema of
the engine; priority and deadline per request type are an assumption of this project
(documented on the "Fuentes de datos" page), not an official city rule.

Fields the public data does not have (first response, contacts, reopenings, load time)
stay empty, and the KPIs that need them are shown as "sin dato en esta fuente".
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import yaml

from ..paths import ROOT
from .download import fetch_paged_csv

CONFIG_PATH = ROOT / "config" / "fuentes.yaml"
ALLOWED_COLUMNS = {"unique_key", "created_date", "closed_date", "agency", "complaint_type",
                   "open_data_channel_type", "status", "borough"}  # fmt: skip


def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["solicitudes"]


def window(cfg: dict, today: pd.Timestamp | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """[start, cutoff): `meses` complete months ending at the end of the previous month."""
    today = (today or pd.Timestamp(datetime.now(UTC).date())).normalize()
    cutoff = today.replace(day=1)  # first day of this month = end of the previous one
    start = cutoff - pd.DateOffset(months=int(cfg["periodo"]["meses"]))
    return start, cutoff


def download(
    cfg: dict | None = None, today: pd.Timestamp | None = None, **kwargs
) -> tuple[pd.DataFrame, dict]:
    cfg = cfg or config()
    start, cutoff = window(cfg, today)
    cols = list(cfg["columnas"])
    if not set(cols) <= ALLOWED_COLUMNS:
        raise ValueError(
            f"columnas no permitidas por privacidad: {sorted(set(cols) - ALLOWED_COLUMNS)}"
        )
    where = (
        f"agency = '{cfg['filtros']['agencia']}' AND created_date >= '{start:%Y-%m-%dT00:00:00}' "
        f"AND created_date < '{cutoff:%Y-%m-%dT00:00:00}'"
    )
    params = {"$select": ",".join(cols), "$where": where, "$order": "unique_key"}
    raw = fetch_paged_csv(
        cfg["api"], params,
        page_size=int(cfg["paginacion"]["tamano_pagina"]), max_rows=int(cfg["paginacion"]["maximo_filas"]),
        min_rows=int(cfg["minimo_filas"]), retries=int(cfg["reintentos"]), **kwargs,
    )  # fmt: skip
    info = {
        "name": cfg["nombre"],
        "publisher": cfg["publicador"],
        "url": cfg["pagina"],
        "downloaded_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "rows": len(raw),
        "filter": f"agencia {cfg['filtros']['agencia']}, creadas entre {start:%Y-%m-%d} y {cutoff - pd.Timedelta(days=1):%Y-%m-%d}",
        "snapshot": f"{cutoff - pd.Timedelta(minutes=1):%Y-%m-%d %H:%M}",
    }
    return raw, info


def to_tickets(raw: pd.DataFrame, cfg: dict, snapshot: pd.Timestamp) -> pd.DataFrame:
    """Map 311 rows to the engine's ticket schema (landing table, before cleaning)."""
    extra = set(raw.columns) - ALLOWED_COLUMNS
    if extra:
        raise ValueError(f"la descarga trae columnas no permitidas: {sorted(extra)}")
    types = cfg["tipos"]
    default = cfg["tipo_por_defecto"]
    complaint = raw["complaint_type"].fillna("")
    label = complaint.map(lambda c: types.get(c, default)["etiqueta"])
    top = label[label != default["etiqueta"]].value_counts().index[: int(cfg["maximo_equipos"])]
    queue = label.where(label.isin(top), default["etiqueta"])
    priority = complaint.map(lambda c: types.get(c, default)["prioridad"])
    created = pd.to_datetime(raw["created_date"], errors="coerce")
    closed = pd.to_datetime(raw["closed_date"], errors="coerce")
    closed = closed.where(
        closed <= snapshot
    )  # closed after the cut-off = still open at the snapshot
    return pd.DataFrame(
        {
            "ticket_id": "NYC" + raw["unique_key"].astype(str),
            "created_at": created,
            "first_response_at": pd.NaT,
            "resolved_at": closed,
            "priority": priority,
            "queue": queue,
            "channel": raw["open_data_channel_type"].map(cfg["canales"]).fillna("Otro"),
            "contacts": float("nan"),
            "reopened": pd.NA,
            "sla_target_hours": priority.map(cfg["plazos_por_prioridad_horas"]).astype(float),
            "status": ["open" if pd.isna(c) else "resolved" for c in closed],
            "borough": raw.get("borough"),
        }
    )
