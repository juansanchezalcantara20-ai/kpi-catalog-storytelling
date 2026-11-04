"""Privacy gate: run before publishing. Fails if personal data could reach the site.

Checks
  1. The landing service-request table has only allowed, non-personal columns.
  2. The built site contains no raw data files (only aggregated numbers inside pages).
  3. No page contains an e-mail address, a phone number or a street address.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .paths import PROCESSED_DIR, ROOT

ALLOWED_TICKET_COLUMNS = {
    "ticket_id", "created_at", "first_response_at", "resolved_at", "priority", "queue", "channel", "contacts",
    "reopened", "sla_target_hours", "status", "borough", "logged_at",
}  # fmt: skip
PERSONAL_HINTS = re.compile(
    r"address|street|name|phone|email|latitude|longitude|location|descriptor|resolution_description|bbl",
    re.I,
)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE = re.compile(r"(?<![\d.])\(?\d{3}\)?[ .-]\d{3}-\d{4}(?![\d])")
ADDRESS = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z0-9][A-Za-z0-9]*\s+){1,3}(?:STREET|AVENUE|ROAD|BOULEVARD|PLACE|PARKWAY|DRIVE|LANE)\b"
)
RAW_FILES = {".csv", ".parquet", ".xlsx", ".zip"}
SKIP = {"plotly.min.js"}


def check_tables(processed: Path = PROCESSED_DIR) -> list[str]:
    problems = []
    path = processed / "landing_tickets.parquet"
    if path.exists():
        cols = set(pd.read_parquet(path).columns)
        extra = cols - ALLOWED_TICKET_COLUMNS
        if extra:
            problems.append(f"columnas no permitidas en las solicitudes: {sorted(extra)}")
        personal = sorted(c for c in cols if PERSONAL_HINTS.search(c))
        if personal:
            problems.append(f"columnas con posibles datos personales: {personal}")
    return problems


def check_site(site: Path) -> list[str]:
    problems = []
    for f in site.rglob("*"):
        if not f.is_file() or f.name in SKIP:
            continue
        if f.suffix.lower() in RAW_FILES:
            problems.append(f"archivo de datos crudos publicado: {f.relative_to(site)}")
            continue
        if f.suffix.lower() not in {
            ".html",
            ".json",
        }:  # pages and the search index (theme assets are third-party code)
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for label, rx in (("correo", EMAIL), ("teléfono", PHONE), ("dirección", ADDRESS)):
            m = rx.search(text)
            if m and not (label == "correo" and m.group(0).endswith((".png", ".js", ".css"))):
                problems.append(f"posible {label} en {f.relative_to(site)}: «{m.group(0)[:40]}»")
    return problems


def main(site: Path = ROOT / "site") -> int:
    problems = check_tables() + (
        check_site(site) if site.exists() else ["no existe la carpeta del sitio"]
    )
    if problems:
        print("Candado de privacidad: NO se publica.")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Candado de privacidad: sin datos personales; solo cifras agregadas.")
    return 0
