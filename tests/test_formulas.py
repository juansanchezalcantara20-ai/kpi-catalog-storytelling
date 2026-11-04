"""Every KPI formula is checked against a hand-calculated example (tests/hand_examples.py)."""

from __future__ import annotations

import math

import pandas as pd
import pytest
from hand_examples import BY_ID, EXAMPLES

from kpistory.catalog import load
from kpistory.engine import Engine
from kpistory.formulas.customers import nps_margin_of_error, retention_series, rfm_table
from kpistory.formulas.maintenance import pm_on_time
from kpistory.formulas.service import derive_ticket_columns

ENGINE = Engine()


def test_every_kpi_has_a_hand_example():
    assert set(BY_ID) == set(load().kpis)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.kpi_id)
def test_formula_matches_hand_calculation(example):
    value = ENGINE.compute(example.kpi_id, example.table, **example.overrides)
    assert value == pytest.approx(example.expected, rel=1e-6), example.working


# ------------------------------------------------------------- edge cases


def test_empty_denominator_is_nan_not_zero():
    empty = pd.DataFrame({"status": [], "resolution_hours": [], "sla_target_hours": []})
    assert math.isnan(ENGINE.compute("sla_compliance", empty))


def test_mtbf_with_zero_failures_is_nan():
    df = pd.DataFrame({"operating_hours": [100.0], "failures": [0]})
    assert math.isnan(ENGINE.compute("mtbf", df))


def test_missing_input_column_raises():
    with pytest.raises(KeyError, match="missing columns"):
        ENGINE.compute("fill_rate", pd.DataFrame({"qty_ordered": [1]}))


def test_derive_ticket_columns_by_hand():
    t = pd.Timestamp
    tickets = pd.DataFrame(
        {
            "created_at": [t("2024-01-01 08:00"), t("2024-01-01 08:00")],
            "first_response_at": [t("2024-01-01 09:30"), pd.NaT],
            "resolved_at": [t("2024-01-02 08:00"), pd.NaT],
            "status": ["resolved", "open"],
            "sla_target_hours": [24.0, 24.0],
        }
    )
    out = derive_ticket_columns(tickets, snapshot=t("2024-01-04 08:00"))
    assert out["first_response_hours"].iloc[0] == pytest.approx(1.5)
    assert out["resolution_hours"].iloc[0] == pytest.approx(24.0)
    assert bool(out["within_sla"].iloc[0]) is True  # 24 <= 24, limit inclusive
    assert out["age_days"].iloc[1] == pytest.approx(3.0)
    assert math.isnan(out["age_days"].iloc[0])


def test_pm_on_time_flag_matches_kpi():
    ex = BY_ID["pm_compliance"]
    pm = ex.table[ex.table["wo_type"].eq("preventive")]
    assert pm_on_time(pm, tolerance_days=3).tolist() == [True, True, False, False]


def test_retention_series_by_hand():
    s = retention_series(BY_ID["retention_rate"].table, "QUARTER")
    assert s.to_dict() == {"2024Q2": 0.5}


def test_rfm_segments_by_hand():
    t = pd.Timestamp
    # Five customers; 'old_loyal' bought often but long ago -> At risk.
    rows = []
    for cid, dates, amount in [
        ("champion", ["2024-12-20", "2024-12-10", "2024-11-01", "2024-10-01"], 100),
        ("old_loyal", ["2024-03-01", "2024-02-01", "2024-01-15", "2024-01-10"], 100),
        ("newbie", ["2024-12-28"], 20),
        ("sleeper", ["2024-02-01"], 10),
        ("middle", ["2024-09-01", "2024-07-01"], 50),
    ]:
        rows += [
            {"customer_id": cid, "invoice_id": f"{cid}{i}", "invoice_date": t(d), "revenue": amount}
            for i, d in enumerate(dates)
        ]
    rfm = rfm_table(pd.DataFrame(rows), snapshot=t("2024-12-31")).set_index("customer_id")
    assert rfm.loc["champion", "segment"] == "Champions"
    assert rfm.loc["old_loyal", "segment"] == "At risk"
    assert rfm.loc["newbie", "segment"] == "New / promising"
    assert rfm.loc["sleeper", "segment"] == "Hibernating"
    assert rfm.loc["old_loyal", "monetary"] == 400


def test_nps_is_not_the_mean_score():
    scores = BY_ID["nps"].table["score"]
    assert scores.mean() == pytest.approx(7.1)
    assert ENGINE.compute("nps", BY_ID["nps"].table) == pytest.approx(20.0)


def test_nps_margin_of_error_by_hand():
    # p = 0.5, d = 0.3 -> variance = 0.5 + 0.3 - 0.2^2 = 0.76; n = 10
    # MoE = 100 * 1.96 * sqrt(0.076) = 54.03 points: n = 10 is far too small.
    assert nps_margin_of_error(BY_ID["nps"].table["score"]) == pytest.approx(54.034, rel=1e-3)


def test_compute_by_groups_and_grades():
    df = pd.DataFrame(
        {"team": ["a", "a", "b"], "qty_ordered": [10, 10, 10], "qty_shipped": [10, 9, 5]}
    )
    out = ENGINE.compute_by("fill_rate", df, by="team").set_index("team")
    assert out.loc["a", "value"] == pytest.approx(0.95)
    assert out.loc["a", "status"] == "green"
    assert out.loc["b", "status"] == "red"
