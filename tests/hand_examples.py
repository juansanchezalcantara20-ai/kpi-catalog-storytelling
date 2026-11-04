"""Hand-calculated examples: one small table per KPI with the expected result written out.

Each example is computed by hand in its `working` string, so a reader can check
the arithmetic without running anything. The same examples are used by
test_formulas.py (Python engine) and test_sql.py (reference SQL), and they are
shown on the KPI pages of the site as "worked example from the test suite".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

T = pd.Timestamp


@dataclass
class HandExample:
    kpi_id: str
    table: pd.DataFrame
    expected: float
    working: str
    overrides: dict[str, Any] = field(default_factory=dict)


def _tickets() -> pd.DataFrame:
    # Five tickets. Hours are already derived (see derive_ticket_columns tests).
    return pd.DataFrame(
        {
            "ticket_id": [1, 2, 3, 4, 5],
            "status": ["resolved", "resolved", "resolved", "resolved", "open"],
            "first_response_hours": [1.0, 3.0, 0.5, 6.0, None],
            "resolution_hours": [10.0, 30.0, 4.0, 50.0, None],
            "sla_target_hours": [24.0, 24.0, 8.0, 72.0, 24.0],
            "contacts": [1, 2, 1, 1, 1],
            "reopened": [False, False, True, False, False],
            "age_days": [None, None, None, None, 9.0],
        }
    )


def _backlog() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "status": ["open", "open", "open", "open", "resolved"],
            "age_days": [2.0, 8.0, 15.0, 7.0, None],
        }
    )


EXAMPLES: list[HandExample] = [
    # ---------------------------------------------------------------- service
    HandExample(
        "first_response_time",
        _tickets(),
        2.0,
        "Responded tickets: 0.5, 1, 3, 6 h (ticket 5 has no response yet). "
        "Median of 4 values = (1 + 3) / 2 = 2.0 h.",
    ),
    HandExample(
        "resolution_time",
        _tickets(),
        20.0,
        "Resolved: 4, 10, 30, 50 h. Median = (10 + 30) / 2 = 20.0 h. "
        "(The mean would be 23.5 h, pulled up by the 50 h ticket.)",
    ),
    HandExample(
        "sla_compliance",
        _tickets(),
        0.75,
        "Within SLA: #1 10<=24 yes, #2 30<=24 no, #3 4<=8 yes, #4 50<=72 yes. "
        "3 of 4 resolved = 0.75. The open ticket is not counted.",
    ),
    HandExample(
        "backlog_aged_share",
        _backlog(),
        0.5,
        "Open tickets aged 2, 8, 15, 7 days. Older than 7 days: 8 and 15 "
        "(exactly 7 is not older). 2 / 4 = 0.5.",
    ),
    HandExample(
        "first_contact_resolution",
        _tickets(),
        0.5,
        "Resolved with 1 contact and not reopened: #1 yes, #2 no (2 contacts), "
        "#3 no (reopened), #4 yes. 2 / 4 = 0.5.",
    ),
    HandExample(
        "reopen_rate",
        _tickets(),
        0.25,
        "Reopened among resolved: only #3. 1 / 4 = 0.25.",
    ),
    # ------------------------------------------------------------ maintenance
    HandExample(
        "mtbf",
        pd.DataFrame(
            {
                "asset_id": ["A", "A", "B"],
                "operating_hours": [400.0, 300.0, 500.0],
                "failures": [2, 0, 1],
            }
        ),
        400.0,
        "Ratio of sums: (400 + 300 + 500) / (2 + 0 + 1) = 1200 / 3 = 400 h. "
        "Averaging per-row MTBF would fail on the 0-failure row.",
    ),
    HandExample(
        "mttr",
        pd.DataFrame(
            {
                "wo_type": ["corrective", "corrective", "corrective", "preventive"],
                "repair_hours": [2.0, 3.0, 10.0, 1.0],
            }
        ),
        5.0,
        "Corrective only: (2 + 3 + 10) / 3 = 5.0 h. The median would be 3.0 h - "
        "one long repair drives the mean.",
    ),
    HandExample(
        "availability",
        pd.DataFrame(
            {
                "scheduled_hours": [160.0, 160.0],
                "unplanned_downtime_hours": [8.0, 0.0],
            }
        ),
        0.975,
        "(320 - 8) / 320 = 312 / 320 = 0.975.",
    ),
    HandExample(
        "pm_compliance",
        pd.DataFrame(
            {
                "wo_type": ["preventive"] * 4 + ["corrective"],
                "due_date": [
                    T("2024-03-01"),
                    T("2024-03-10"),
                    T("2024-03-20"),
                    T("2024-03-25"),
                    T("2024-03-05"),
                ],
                "completed_at": [
                    T("2024-03-01"),
                    T("2024-03-13"),
                    T("2024-03-24"),
                    pd.NaT,
                    T("2024-03-30"),
                ],
            }
        ),
        0.5,
        "Tolerance 3 days. PM1 on the day: on time. PM2 +3 days: on time (limit inclusive). "
        "PM3 +4 days: late. PM4 not done: late. Corrective ignored. 2 / 4 = 0.5.",
    ),
    HandExample(
        "planned_work_share",
        pd.DataFrame({"planned": [True, True, False], "labor_hours": [4.0, 2.0, 6.0]}),
        0.5,
        "Planned hours 4 + 2 = 6 of 12 total = 0.5 (counting work orders would give 2/3).",
    ),
    # -------------------------------------------------------------- inventory
    HandExample(
        "fill_rate",
        pd.DataFrame({"qty_ordered": [10, 5, 5], "qty_shipped": [10, 3, 5]}),
        0.9,
        "Shipped 18 of 20 units ordered = 0.9.",
    ),
    HandExample(
        "otif",
        pd.DataFrame(
            {
                "order_id": [1, 1, 2, 3, 4],
                "qty_ordered": [5, 5, 4, 2, 3],
                "qty_shipped": [5, 5, 4, 1, 3],
                "promised_date": [T("2024-01-10")] * 5,
                "delivered_date": [
                    T("2024-01-09"),
                    T("2024-01-10"),
                    T("2024-01-11"),
                    T("2024-01-10"),
                    T("2024-01-10"),
                ],
            }
        ),
        0.5,
        "Order 1: both lines full and on time -> OK. Order 2: one day late -> fail. "
        "Order 3: short (1 of 2) -> fail. Order 4: OK. 2 OK of 4 orders = 0.5. "
        "Fill rate on the same data is 18/19 = 94.7%: OTIF is stricter.",
    ),
    HandExample(
        "inventory_turnover",
        pd.DataFrame(
            {
                "date": [T("2024-01-01"), T("2024-01-01"), T("2024-01-02"), T("2024-01-02")],
                "sku": ["a", "b", "a", "b"],
                "on_hand_value": [100.0, 100.0, 50.0, 150.0],
                "cogs_value": [5.0, 5.0, 5.0, 5.0],
            }
        ),
        18.25,
        "COGS 20 over 2 days, annualised: 20 * 365 / 2 = 3650. Inventory value per date: "
        "100 + 100 = 200 and 50 + 150 = 200, average 200. Turnover = 3650 / 200 = 18.25x / year.",
    ),
    HandExample(
        "days_of_cover",
        pd.DataFrame(
            {
                "date": [T("2024-01-01"), T("2024-01-02"), T("2024-01-03")],
                "on_hand_units": [100, 90, 60],
                "demand_units": [10, 10, 10],
            }
        ),
        6.0,
        "Average daily demand = 30 / 3 = 10 units. Stock on the last date = 60. 60 / 10 = 6.0 days.",
    ),
    HandExample(
        "stockout_rate",
        pd.DataFrame(
            {
                "on_hand_units": [0, 5, 3, 0, 10, 2, 0, 1, 0, 0],
                "active": [True] * 8 + [False, False],
            }
        ),
        0.375,
        "Active SKU-days: 8 (the last two rows are a discontinued SKU and are excluded). "
        "At zero: 3 of 8 = 0.375. Counting the inactive rows would give 5 / 10 = 0.5.",
    ),
    HandExample(
        "obsolescence_share",
        pd.DataFrame(
            {"on_hand_value": [500.0, 300.0, 200.0], "days_since_last_movement": [10, 200, 181]}
        ),
        0.5,
        "Limit 180 days. Older: 300 + 200 = 500 of 1000 total value = 0.5.",
    ),
    HandExample(
        "mape",
        pd.DataFrame({"actual_units": [100, 10, 0], "forecast_units": [90, 20, 5]}),
        0.55,
        "Row 3 dropped (actual 0). |100-90|/100 = 0.10; |10-20|/10 = 1.00. "
        "Mean (0.10 + 1.00) / 2 = 0.55. The small SKU dominates.",
    ),
    HandExample(
        "wape",
        pd.DataFrame({"actual_units": [100, 10, 0], "forecast_units": [90, 20, 5]}),
        25 / 110,
        "Sum |A-F| = 10 + 10 + 5 = 25. Sum A = 110. 25 / 110 = 0.22727. "
        "Same data as MAPE: 22.7% vs 55%.",
    ),
    HandExample(
        "forecast_bias",
        pd.DataFrame({"actual_units": [100, 10, 0], "forecast_units": [90, 20, 5]}),
        5 / 110,
        "(115 - 110) / 110 = +0.04545 -> 4.5% over-forecast, inside the +/-5% band.",
    ),
    # -------------------------------------------------------------- customers
    HandExample(
        "retention_rate",
        pd.DataFrame(
            {
                "customer_id": ["a", "b", "c", "d", "a", "c", "e"],
                "invoice_date": [
                    T("2024-01-15"),
                    T("2024-02-01"),
                    T("2024-03-30"),
                    T("2024-03-01"),
                    T("2024-04-02"),
                    T("2024-05-20"),
                    T("2024-06-01"),
                ],
            }
        ),
        0.5,
        "Q1 customers: a, b, c, d. Q2 customers: a, c, e. Retained = a, c. "
        "2 / 4 = 0.5 (new customer e does not count).",
    ),
    HandExample(
        "repeat_purchase_rate",
        pd.DataFrame(
            {
                "customer_id": ["a", "a", "a", "b", "b", "c"],
                "invoice_id": ["i1", "i1", "i2", "i3", "i3", "i4"],
            }
        ),
        1 / 3,
        "Distinct invoices: a = 2 (i1, i2), b = 1 (two lines of i3), c = 1. "
        "1 of 3 customers repeats = 0.3333. Counting lines would wrongly give 2/3.",
    ),
    HandExample(
        "revenue_at_risk_share",
        pd.DataFrame(
            {
                "segment": ["Champions", "At risk", "At risk", "Hibernating"],
                "monetary": [500.0, 200.0, 100.0, 200.0],
            }
        ),
        0.3,
        "At risk revenue 200 + 100 = 300 of 1000 = 0.3.",
    ),
    HandExample(
        "nps",
        pd.DataFrame({"score": [10, 9, 9, 8, 7, 6, 3, 10, 0, 9]}),
        20.0,
        "Promoters (9-10): 10, 9, 9, 10, 9 = 5. Detractors (0-6): 6, 3, 0 = 3. "
        "Passives: 2. NPS = 100 * (5 - 3) / 10 = +20. The mean score 7.1 is not NPS.",
    ),
    # ----------------------------------------------------------- data quality
    HandExample(
        "dq_completeness",
        pd.DataFrame(
            {"id": [1, 2, 3, 4], "customer": ["x", None, "", "y"], "amount": [1.0, 2.0, None, 4.0]}
        ),
        0.625,
        "Required columns customer, amount: 4 rows x 2 = 8 cells. customer is missing twice "
        "(None and a blank string), amount once. 5 filled of 8 = 0.625.",
        overrides={"columns": ["customer", "amount"]},
    ),
    HandExample(
        "dq_uniqueness",
        pd.DataFrame({"ticket_id": [1, 2, 2, 3, 3]}),
        0.6,
        "Distinct keys 1, 2, 3 = 3 of 5 rows = 0.6.",
        overrides={"key": ["ticket_id"]},
    ),
    HandExample(
        "dq_validity",
        pd.DataFrame({"quantity": [5, -1, 3, 0], "price": [2.0, 2.0, -1.0, 1.0]}),
        0.25,
        "Rules: quantity > 0 and price >= 0. Row 1 passes; row 2 fails quantity; "
        "row 3 fails price; row 4 fails quantity. 1 / 4 = 0.25 (rows, not rule failures).",
        overrides={"rules": ["quantity > 0", "price >= 0"]},
    ),
    HandExample(
        "dq_timeliness",
        pd.DataFrame(
            {
                "event_at": [T("2024-01-01 08:00")] * 4,
                "loaded_at": [
                    T("2024-01-01 09:00"),
                    T("2024-01-02 08:00"),
                    T("2024-01-02 08:01"),
                    T("2024-01-05"),
                ],
            }
        ),
        0.5,
        "Max delay 24 h. Delays 1 h, 24 h (inclusive, on time), 24 h 1 min, 88 h. 2 / 4 = 0.5.",
        overrides={"event_col": "event_at", "loaded_col": "loaded_at", "max_delay_hours": 24},
    ),
]

BY_ID = {e.kpi_id: e for e in EXAMPLES}
