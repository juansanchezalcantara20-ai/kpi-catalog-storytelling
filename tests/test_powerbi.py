"""The committed Power BI files are exactly what the catalog generates, and every KPI has a measure."""

from __future__ import annotations

import json
import re

from kpistory.catalog import load
from kpistory.paths import POWERBI_DIR
from kpistory.powerbi.export import (
    HOME_TABLE,
    MODEL,
    RELATIONSHIPS,
    checklist,
    measure_name,
    measures_dax,
    model_md,
    theme_json,
)

C = load()


def test_committed_files_are_up_to_date():
    assert (POWERBI_DIR / "measures.dax").read_text(encoding="utf-8") == measures_dax(C), (
        "run `kpistory powerbi`"
    )
    assert (POWERBI_DIR / "MODEL.md").read_text(encoding="utf-8") == model_md(C)
    assert (POWERBI_DIR / "BUILD_CHECKLIST.md").read_text(encoding="utf-8") == checklist(C)
    assert json.loads((POWERBI_DIR / "theme.json").read_text(encoding="utf-8")) == json.loads(
        theme_json()
    )


def test_every_kpi_is_a_measure_with_balanced_parentheses():
    dax = measures_dax(C)
    assert "${" not in dax
    for k in C:
        assert f"[{measure_name(k)}] =" in dax
        expr = k.dax_expression
        assert expr.count("(") == expr.count(")"), k.id


def test_measure_names_are_unique_and_safe():
    names = [measure_name(k) for k in C]
    assert len(set(names)) == len(names)
    assert all(re.fullmatch(r"[A-Za-z0-9 %-]+", n) for n in names)


def test_measures_only_reference_modelled_tables():
    tables = {t.name for t in MODEL} | {"Date"}
    for k in C:
        assert HOME_TABLE[k.input["table"]] in tables
        for ref in re.findall(r"'?([A-Za-z]+)'?\[", k.dax_expression):
            assert ref in tables, f"{k.id} references unknown table {ref}"


def test_relationships_use_modelled_columns():
    cols = {t.name: set(t.columns) for t in MODEL} | {"Date": {"Date"}}
    for one, one_col, many, many_col in RELATIONSHIPS:
        assert one_col in cols[one] and many_col in cols[many]
