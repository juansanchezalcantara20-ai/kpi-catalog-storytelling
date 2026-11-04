"""Repository paths, resolved from the package location."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KPIS_DIR = ROOT / "kpis"
CATALOG_PATH = KPIS_DIR / "catalog.yaml"
SCHEMA_PATH = KPIS_DIR / "catalog.schema.json"
DQ_RULES_PATH = KPIS_DIR / "dq_rules.yaml"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DOCS_DIR = ROOT / "docs"
TESTS_DIR = ROOT / "tests"
