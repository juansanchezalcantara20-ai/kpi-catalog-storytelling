"""Data layer: deterministic generators, real-schema parsers, plan-B fallback, simulation invariants."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from kpistory.data import customers, inventory, maintenance, pipeline, quality, retail, tickets
from kpistory.engine import Engine

E = Engine()


@pytest.fixture(scope="module")
def small_sales():
    return retail.clean(retail.generate(n_customers=300, n_skus=150))


def test_ticket_generator_is_deterministic():
    a, b = tickets.generate(), tickets.generate()
    pd.testing.assert_frame_equal(a, b)


def test_ticket_cleaning_removes_duplicates_and_impossible_times():
    landing = tickets.generate()
    clean = tickets.clean(landing)
    assert landing["ticket_id"].duplicated().any()
    assert not clean["ticket_id"].duplicated().any()
    assert not (clean["resolved_at"] < clean["created_at"]).any()
    assert clean.loc[clean["status"].eq("open"), "resolved_at"].isna().all()


def test_ai4i_plan_b_follows_published_rules():
    df = maintenance.generate_ai4i(n=3000)
    assert list(df.columns) == maintenance.AI4I_COLUMNS
    # OSF rule: tool wear x torque above the type limit always fails.
    limit = df["Type"].map({"L": 11000, "M": 12000, "H": 13000})
    assert (df.loc[df["Tool wear [min]"] * df["Torque [Nm]"] > limit, "OSF"] == 1).all()
    assert (df["Machine failure"] == (df[maintenance.FAILURE_MODES].sum(axis=1) > 0)).all()


def test_ai4i_parser_accepts_the_real_schema():
    csv = (
        ",".join(maintenance.AI4I_COLUMNS)
        + "\n"
        + "1,M14860,M,298.1,308.6,1551,42.8,0,0,0,0,0,0,0\n"
    )
    df = maintenance.parse_ai4i(io.StringIO(csv))
    assert df.loc[0, "Product ID"] == "M14860"
    with pytest.raises(ValueError, match="expected columns"):
        maintenance.parse_ai4i(io.StringIO("a,b\n1,2\n"))


def test_retail_parser_accepts_the_real_schema():
    sheet = pd.DataFrame(
        {
            "Invoice": [489434, "C489449"],
            "StockCode": [85048, "22087"],
            "Description": ["15CM CHRISTMAS GLASS BALL 20 LIGHTS", "PAPER BUNTING WHITE LACE"],
            "Quantity": [12, -12],
            "InvoiceDate": ["2009-12-01 07:45:00", "2009-12-01 10:33:00"],
            "Price": [6.95, 2.95],
            "Customer ID": [13085.0, None],
            "Country": ["United Kingdom", "Australia"],
        }
    )
    df = retail.parse_retail_frames([sheet, sheet.iloc[:1]])
    assert len(df) == 3 and df["Invoice"].iloc[0] == "489434"
    clean = retail.clean(df)
    assert len(clean) == 1  # cancellation and exact duplicate removed
    assert clean["revenue"].iloc[0] == pytest.approx(83.4)


def test_auto_source_falls_back_to_plan_b():
    def broken():
        raise OSError("network down")

    df, info = pipeline._acquire("process_data", broken, lambda: pd.DataFrame({"x": [1]}), "auto")
    assert info["origin"] == "synthetic" and "network down" in info["note"]
    with pytest.raises(OSError):
        pipeline._acquire("process_data", broken, lambda: pd.DataFrame(), "real")


def test_inventory_simulation_invariants(small_sales):
    out = inventory.simulate(small_sales)
    daily, lines = out["inventory_daily"], out["order_lines"]
    assert (daily["on_hand_units"] >= 0).all()
    assert (daily["shipped_units"] <= daily["demand_units"]).all()
    assert (lines["qty_shipped"] <= lines["qty_ordered"]).all()
    # Every shipped unit in the daily table is allocated to an order line.
    assert daily["shipped_units"].sum() == pytest.approx(lines["qty_shipped"].sum())
    assert set(out["forecast"].columns) >= {"sku", "week", "actual_units", "forecast_units"}


def test_survey_cleaning(small_sales):
    rfm = customers.build_rfm(small_sales)
    landing = customers.generate_survey(rfm)
    clean = customers.clean_survey(landing)
    assert clean["score"].between(0, 10).all()
    assert not clean["response_id"].duplicated().any()


def test_dq_measure_matches_the_catalog_kpis():
    landing = {"tickets": tickets.generate().head(2000)}
    rules = quality.load_rules()
    cfg = rules["tickets"]
    out = quality.measure(landing | _empty_like_other_datasets(rules))["dq_results"]
    row = out[(out["dataset"] == "tickets") & (out["dimension"] == "completeness")].iloc[0]
    assert row["value"] == pytest.approx(
        E.compute("dq_completeness", landing["tickets"], columns=cfg["required"])
    )
    row = out[(out["dataset"] == "tickets") & (out["dimension"] == "uniqueness")].iloc[0]
    assert row["value"] == pytest.approx(
        E.compute("dq_uniqueness", landing["tickets"], key=cfg["key"])
    )


def _empty_like_other_datasets(rules):
    """Tiny valid frames for the datasets not under test."""
    t = pd.Timestamp("2024-01-01")
    return {
        "work_orders": pd.DataFrame(
            {"wo_id": ["a"], "asset_id": ["M01"], "wo_type": ["preventive"], "created_at": [t],
             "labor_hours": [1.0], "failure_mode": [None], "completed_at": [t], "logged_at": [t]}
        ),
        "process_data": maintenance.generate_ai4i(n=10),
        "transactions": pd.DataFrame(
            {"Invoice": ["1"], "StockCode": ["123"], "Description": ["x"], "Quantity": [1], "InvoiceDate": [t],
             "Price": [1.0], "Customer ID": [1.0], "Country": ["UK"]}
        ),
        "survey": pd.DataFrame(
            {"response_id": ["r"], "customer_id": ["1"], "score": [9], "responded_at": [t], "loaded_at": [t]}
        ),
    }  # fmt: skip
