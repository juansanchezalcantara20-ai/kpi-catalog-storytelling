"""Traffic-light grading and formatting follow the catalog thresholds."""

from __future__ import annotations

import pytest

from kpistory.engine import Engine, format_threshold

E = Engine()


@pytest.mark.parametrize(
    ("kpi_id", "value", "expected"),
    [
        ("sla_compliance", 0.90, "green"),  # higher is better, green >= 0.90 (inclusive)
        ("sla_compliance", 0.87, "amber"),
        ("sla_compliance", 0.80, "red"),
        ("mttr", 4.0, "green"),  # lower is better, green <= 4
        ("mttr", 5.5, "amber"),
        ("mttr", 9.0, "red"),
        ("days_of_cover", 21.0, "green"),  # target range [14, 35]
        ("days_of_cover", 10.0, "amber"),  # below green band, inside amber [7, 60]
        ("days_of_cover", 45.0, "amber"),  # above green band: too much stock is also bad
        ("days_of_cover", 90.0, "red"),
        ("forecast_bias", -0.12, "red"),
        ("forecast_bias", float("nan"), "n/a"),
    ],
)
def test_grade(kpi_id, value, expected):
    assert E.status(kpi_id, value) == expected


def test_format():
    assert E.format("sla_compliance", 0.8766) == "87.7%"
    assert E.format("mttr", 4.25) == "4.2 h"
    assert E.format("nps", 23.4) == "+23"
    assert E.format("nps", float("nan")) == "n/a"


def test_format_threshold():
    assert format_threshold(E.catalog["sla_compliance"]) == "≥ 90.0% (amber ≥ 85.0%)"
    assert format_threshold(E.catalog["days_of_cover"]).startswith("14.0 days to 35.0 days")
