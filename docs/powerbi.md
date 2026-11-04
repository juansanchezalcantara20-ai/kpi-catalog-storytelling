# Power BI layer

!!! warning "What is and is not done"
    The Power BI files are **generated from the catalog but were not executed in Power BI Desktop** - Desktop does not run in the environment where this repository was built, so a PBIP/TMDL project could not be validated. Instead the repository ships the DAX measures, the star schema and a build checklist. Nothing on this page is a screenshot of a Power BI report.

## What is generated

| File | Content |
|---|---|
| [`powerbi/measures.dax`](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/blob/main/powerbi/measures.dax) | All 28 KPIs as DAX measures, ready for DAX query view, with an `EVALUATE` that returns every KPI in one row |
| [`powerbi/MODEL.md`](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/blob/main/powerbi/MODEL.md) | Star schema: fact and dimension tables, columns and types, 16 relationships |
| [`powerbi/BUILD_CHECKLIST.md`](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/blob/main/powerbi/BUILD_CHECKLIST.md) | Step-by-step assembly in Power BI Desktop, including a reconciliation step |
| [`powerbi/theme.json`](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/blob/main/powerbi/theme.json) | The site's palette as a Power BI report theme |
| [`data/powerbi/*.csv`](https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/data/powerbi/manifest.json) on this site | The model tables and `expected_values.csv` (Python results), rebuilt by GitHub Actions on every push - load them in Power BI with *Get data → Web* |

## Why this proves the point of the repository

The DAX below is not written for Power BI: it is stored in `kpis/catalog.yaml` next to the definition, the Python function and the SQL. Parameters such as the 7-day backlog limit are substituted from the catalog, so changing a rule changes all three implementations. The reconciliation step (`EVALUATE` vs `expected_values.csv`) checks that the DAX returns the same numbers as the tested Python engine.

## Measures

| Measure | Home table | Format | Target |
|---|---|---|---|
| [First response time median](catalog/first_response_time.md) | Tickets | `0.0 "h"` | ≤ 2.0 h (amber ≤ 4.0 h) |
| [Resolution time median](catalog/resolution_time.md) | Tickets | `0.0 "h"` | ≤ 24.0 h (amber ≤ 36.0 h) |
| [SLA compliance](catalog/sla_compliance.md) | Tickets | `0.0%` | ≥ 90.0% (amber ≥ 85.0%) |
| [Aged backlog 7 days](catalog/backlog_aged_share.md) | Tickets | `0.0%` | ≤ 10.0% (amber ≤ 20.0%) |
| [First contact resolution FCR](catalog/first_contact_resolution.md) | Tickets | `0.0%` | ≥ 70.0% (amber ≥ 60.0%) |
| [Reopen rate](catalog/reopen_rate.md) | Tickets | `0.0%` | ≤ 5.0% (amber ≤ 8.0%) |
| [Mean time between failures MTBF](catalog/mtbf.md) | AssetPeriods | `0.0 "h"` | ≥ 150.0 h (amber ≥ 100.0 h) |
| [Mean time to repair MTTR](catalog/mttr.md) | WorkOrders | `0.0 "h"` | ≤ 4.0 h (amber ≤ 6.0 h) |
| [Availability](catalog/availability.md) | AssetPeriods | `0.0%` | ≥ 97.0% (amber ≥ 95.0%) |
| [Preventive maintenance compliance](catalog/pm_compliance.md) | WorkOrders | `0.0%` | ≥ 90.0% (amber ≥ 80.0%) |
| [Planned maintenance share](catalog/planned_work_share.md) | WorkOrders | `0.0%` | ≥ 80.0% (amber ≥ 65.0%) |
| [Fill rate units](catalog/fill_rate.md) | OrderLines | `0.0%` | ≥ 95.0% (amber ≥ 90.0%) |
| [On time in full OTIF](catalog/otif.md) | OrderLines | `0.0%` | ≥ 90.0% (amber ≥ 80.0%) |
| [Inventory turnover](catalog/inventory_turnover.md) | InventoryDaily | `0.0"x"` | ≥ 8.0x / year (amber ≥ 5.0x / year) |
| [Days of cover](catalog/days_of_cover.md) | InventoryDaily | `0.0 "d"` | 14.0 days to 35.0 days (amber 7.0 days to 60.0 days) |
| [Stockout rate SKU-days](catalog/stockout_rate.md) | InventoryDaily | `0.0%` | ≤ 3.0% (amber ≤ 6.0%) |
| [Obsolete stock share](catalog/obsolescence_share.md) | InventorySnapshot | `0.0%` | ≤ 5.0% (amber ≤ 10.0%) |
| [Forecast error MAPE](catalog/mape.md) | Forecast | `0.0%` | ≤ 40.0% (amber ≤ 60.0%) |
| [Forecast error WAPE](catalog/wape.md) | Forecast | `0.0%` | ≤ 30.0% (amber ≤ 45.0%) |
| [Forecast bias](catalog/forecast_bias.md) | Forecast | `0.0%` | -5.0% to 5.0% (amber -10.0% to 10.0%) |
| [Customer retention quarter over quarter](catalog/retention_rate.md) | Sales | `0.0%` | ≥ 50.0% (amber ≥ 40.0%) |
| [Repeat purchase rate](catalog/repeat_purchase_rate.md) | Sales | `0.0%` | ≥ 60.0% (amber ≥ 50.0%) |
| [Revenue at risk RFM At risk](catalog/revenue_at_risk_share.md) | Sales | `0.0%` | ≤ 10.0% (amber ≤ 20.0%) |
| [Net Promoter Score simulated survey](catalog/nps.md) | Survey | `+0;-0;0` | ≥ +30 (amber ≥ +10) |
| [Completeness](catalog/dq_completeness.md) | DQResults | `0.0%` | ≥ 99.0% (amber ≥ 95.0%) |
| [Uniqueness](catalog/dq_uniqueness.md) | DQResults | `0.0%` | ≥ 99.9% (amber ≥ 99.0%) |
| [Validity](catalog/dq_validity.md) | DQResults | `0.0%` | ≥ 98.0% (amber ≥ 95.0%) |
| [Timeliness](catalog/dq_timeliness.md) | DQResults | `0.0%` | ≥ 95.0% (amber ≥ 90.0%) |

## Three examples

**SLA compliance** - What share of tickets did we resolve within the time we promised?

```dax
SLA compliance =
DIVIDE (
    CALCULATE ( COUNTROWS ( Tickets ), Tickets[status] = "resolved", Tickets[within_sla] = TRUE () ),
    CALCULATE ( COUNTROWS ( Tickets ), Tickets[status] = "resolved" )
)
```

**On time in full (OTIF)** - How many orders arrived complete and on the promised date?

```dax
On time in full OTIF =
VAR _orders = VALUES ( OrderLines[order_id] )
VAR _ok =
    COUNTROWS (
        FILTER (
            _orders,
            CALCULATE (
                ISEMPTY (
                    FILTER (
                        OrderLines,
                        OrderLines[qty_shipped] < OrderLines[qty_ordered]
                            || ISBLANK ( OrderLines[delivered_date] )
                            || OrderLines[delivered_date] > OrderLines[promised_date]
                    )
                )
            )
        )
    )
RETURN DIVIDE ( _ok, COUNTROWS ( _orders ) )
```

**Customer retention (quarter over quarter)** - Of the customers who bought last quarter, how many bought again this quarter?

```dax
Customer retention quarter over quarter =
VAR _current = VALUES ( Sales[customer_id] )
VAR _previous = CALCULATETABLE ( VALUES ( Sales[customer_id] ), DATEADD ( 'Date'[Date], -1, QUARTER ) )
RETURN DIVIDE ( COUNTROWS ( INTERSECT ( _previous, _current ) ), COUNTROWS ( _previous ) )
```
