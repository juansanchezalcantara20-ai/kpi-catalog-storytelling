"""Dashboard payload: JSON-safe values and one series per catalog KPI."""

from __future__ import annotations

import json
import math

import pytest

from kpistory.catalog import load
from kpistory.dashboard import PAGE, _clean, payload
from kpistory.engine import Engine
from kpistory.paths import PROCESSED_DIR


def test_clean_makes_values_json_safe():
    out = _clean({"a": float("nan"), "b": [1.23456789, float("inf")], "c": "x"})
    assert out == {"a": None, "b": [1.234568, None], "c": "x"}
    json.dumps(out, allow_nan=False)


def test_page_template_has_a_slot_for_every_token():
    for token in ("__PAYLOAD__", "__HIGHLIGHT__", "__NKPI__", "__DATA_NOTE__"):
        assert token in PAGE


@pytest.mark.skipif(
    not (PROCESSED_DIR / "manifest.json").exists(), reason="run `kpistory data` first"
)
def test_payload_covers_every_kpi():
    from kpistory.data.pipeline import load_tables

    tables, manifest = load_tables()
    data = payload(tables, Engine(), manifest)
    assert {k["id"] for k in data["kpis"]} == set(load().kpis)
    for k in data["kpis"]:
        assert k["series"]["x"], k["id"]
        assert k["value"] is None or not math.isnan(k["value"])
    json.dumps(data, allow_nan=False)
