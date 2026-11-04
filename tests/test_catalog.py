"""The catalog is structurally and semantically valid, and invalid catalogs are rejected."""

from __future__ import annotations

import copy

import pytest

from kpistory.catalog import CatalogError, load, load_raw, validate

RAW = load_raw()


def test_catalog_is_valid():
    validate(RAW)
    assert len(load()) == len(RAW["kpis"])


def test_every_case_has_kpis():
    c = load()
    for case in c.cases:
        assert c.for_case(case), case


def test_no_pie_charts_in_catalog():
    assert all(k.chart["type"] != "pie" for k in load())


def test_params_are_rendered_in_dax_and_sql():
    k = load()["backlog_aged_share"]
    assert "${" not in k.dax_expression and "> 7" in k.dax_expression
    assert "> 7" in k.sql_query


def _broken(mutate):
    raw = copy.deepcopy(RAW)
    mutate(raw)
    with pytest.raises(CatalogError) as err:
        validate(raw)
    return str(err.value)


def test_rejects_duplicate_id():
    msg = _broken(lambda r: r["kpis"].append(copy.deepcopy(r["kpis"][0])))
    assert "duplicate" in msg


def test_rejects_unknown_related():
    msg = _broken(lambda r: r["kpis"][0]["related"].append("does_not_exist"))
    assert "does_not_exist" in msg


def test_rejects_inconsistent_thresholds():
    def mutate(r):
        k = next(k for k in r["kpis"] if k["id"] == "sla_compliance")
        k["thresholds"] = {"green": 0.80, "amber": 0.90}

    assert "green >= amber" in _broken(mutate)


def test_rejects_missing_field():
    msg = _broken(lambda r: r["kpis"][0].pop("misreadings"))
    assert "misreadings" in msg


def test_rejects_question_without_question_mark():
    def mutate(r):
        r["kpis"][0]["question"] = "Not a question"

    assert "schema" in _broken(mutate)


def test_rejects_unknown_param_reference():
    def mutate(r):
        r["kpis"][0]["dax"] = "SUM ( T[x] ) > ${nope}"

    assert "unknown param 'nope'" in _broken(mutate)


def test_rejects_kpi_without_python_implementation():
    def mutate(r):
        k = copy.deepcopy(r["kpis"][0])
        k["id"] = "brand_new_kpi"
        k["related"] = []
        r["kpis"].append(k)

    assert "without a Python implementation" in _broken(mutate)
